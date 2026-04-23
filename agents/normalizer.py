"""Normalizer agent — Haiku 4.5.

Converts colloquial Bahasa Indonesia clinical queries into a structured
`NormalizedQuery`. Refuses if the query is out of medical scope or asks
for a patient-specific decision.

One shot, no retries. Per CLAUDE.md: "If output is malformed, orchestrator
refuses." We surface that as a `NormalizerRefusal` with
`RefusalReason.NORMALIZER_MALFORMED` so the orchestrator can emit a
clean refusal.

Transport errors (Anthropic client failures) propagate — per the
"Errors loud, not swallowed" rule.
"""

from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Any, Protocol

import structlog
from pydantic import ValidationError

from agents.base import NormalizerRefusal, NormalizerResult
from core.refusals import RefusalReason
from core.state import NormalizedQuery, QueryState

log = structlog.get_logger("anamnesa.agents.normalizer")

DEFAULT_MODEL_ID = "claude-haiku-4-5-20251001"
MAX_OUTPUT_TOKENS = 800
PROMPT_PATH = Path(__file__).parent / "prompts" / "normalizer.md"


# ---------------------------------------------------------------------------
# Pre-LLM heuristic — catch obvious non-clinical queries without paying the
# Haiku round-trip. Conservative by design: we only short-circuit queries
# that are unambiguously not medical. Anything that COULD be clinical still
# goes to Haiku.
# ---------------------------------------------------------------------------

# Whole-word / phrase hits that are unambiguously non-clinical. Keeping
# the list deliberately short — each hit must be a true non-medical
# signal in every realistic Indonesian context. Mixed with "_prefix" for
# startswith checks to catch imperative openers.
_NON_MEDICAL_PHRASES: tuple[str, ...] = (
    # Greetings / chit-chat
    "apa kabar", "selamat pagi", "selamat siang", "selamat sore",
    "selamat malam", "terima kasih", "hi ", "hello ", "halo ",
    # Jokes / entertainment
    "tell me a joke", "ceritakan lelucon", "tolong buat lelucon",
    # Cooking / recipes (only as the subject — "resep" alone is clinical!)
    "resep nasi", "resep masakan", "resep kue", "resep soto",
    "resep ayam", "resep sambal", "resep mie", "resep rendang",
    # Weather / geography
    "cuaca ", "suhu jakarta", "suhu bandung", "ibukota ",
    "capital of ", "what is the weather",
    # Coding / software
    "write code", "write a function", "python function", "sql query",
    "regex untuk", "tulis kode", "buat script", "javascript code",
    # Money / business
    "harga emas", "harga saham", "kurs dollar", "rate usd",
    "tips jualan", "cara dagang",
    # Current events / news
    "presiden sekarang", "berita terbaru", "news today",
    # Math / arithmetic (outside dosage calc context)
    "berapa 1+1", "berapa 2+2", "what is 2+2", "1 plus 1",
)

# Common medical tokens — if ANY appear in the query, we do NOT short-
# circuit. Prevents false positives like "resep asam mefenamat" (a
# prescription query that starts with "resep" but is clinical).
_CLINICAL_SAFETY_TOKENS: frozenset[str] = frozenset({
    # Conditions
    "dbd", "demam", "dengue", "tb", "tuberkulosis", "hipertensi",
    "diabetes", "dm", "stroke", "infark", "asma", "ppok", "sepsis",
    "pneumonia", "ispa", "gagal", "jantung", "ginjal", "hepar",
    "covid", "hiv", "malaria", "tifoid", "cacar", "campak",
    # Anatomy
    "jantung", "paru", "ginjal", "hati", "lambung", "usus", "otak",
    "tulang", "sendi", "mata", "telinga", "hidung", "kulit",
    # Drug stems
    "amoksisilin", "parasetamol", "ibuprofen", "metformin",
    "insulin", "oat", "rhze", "antibiotik", "analgetik", "nsaid",
    "kortikosteroid", "furosemid", "ramipril", "amlodipin",
    "mg/kg", "mg/kgbb", "mcg", "unit/kg", "dosis",
    # Procedures
    "vtp", "rjp", "cpr", "iv", "im", "sc", "po", "pct",
    # Populations / intents
    "pasien", "anak", "bayi", "balita", "neonatus", "ibu hamil",
    "hamil", "lansia", "geriatri",
    "tata laksana", "tatalaksana", "tatalaksana", "diagnosis",
    "rujukan", "tanda", "gejala", "sindrom", "keluhan",
})


def _is_obviously_non_medical(query: str) -> bool:
    """Return True when the query is almost certainly not clinical.
    Conservative: false negatives (clinical queries mis-classified as
    non-medical) are MUCH worse than false positives (non-medical
    queries that go through to Haiku), so when in doubt we return
    False. Only when (a) a non-medical phrase hits AND (b) zero
    clinical tokens appear do we short-circuit.
    """
    text = query.lower().strip()
    if not text:
        return False
    # Short-circuit trivially-empty / numeric-only queries.
    if text.isnumeric():
        return True
    # Must hit a non-medical phrase...
    hit = any(phrase in text for phrase in _NON_MEDICAL_PHRASES)
    if not hit:
        return False
    # ...AND have zero clinical safety tokens.
    for tok in _CLINICAL_SAFETY_TOKENS:
        if tok in text:
            return False
    return True


class NormalizerPromptError(RuntimeError):
    """Raised if the system prompt file is missing or unreadable."""


def _load_system_prompt() -> str:
    try:
        return PROMPT_PATH.read_text(encoding="utf-8")
    except OSError as exc:  # pragma: no cover - would fail all tests, not unit-testable
        raise NormalizerPromptError(
            f"Normalizer prompt not found at {PROMPT_PATH}"
        ) from exc


class _AnthropicLike(Protocol):
    """Minimal shape of the Anthropic SDK client we depend on.

    Tests inject a fake matching this shape; production code builds a
    real `anthropic.Anthropic` via `_build_client`.
    """

    messages: Any


def _build_client(api_key: str) -> _AnthropicLike:
    """Factory for the real Anthropic client. Local import to avoid
    loading the SDK when tests inject a fake."""
    from anthropic import Anthropic

    return Anthropic(api_key=api_key)


def _extract_text(response: Any) -> str:
    """Pick the first text block out of a Messages API response.

    The Anthropic Messages API returns `content` as a list of blocks
    (TextBlock, ToolUseBlock, etc.). The Normalizer asks for plain JSON
    so we expect exactly one TextBlock. If the response shape is
    unexpected, return empty string — caller will treat as malformed.
    """
    content = getattr(response, "content", None)
    if not content:
        return ""
    for block in content:
        text = getattr(block, "text", None)
        if isinstance(text, str):
            return text
        # dict-shaped fakes
        if isinstance(block, dict) and block.get("type") == "text":
            return str(block.get("text", ""))
    return ""


def _parse_usage(response: Any, model_id: str) -> dict[str, Any]:
    usage = getattr(response, "usage", None)
    input_tokens = getattr(usage, "input_tokens", 0) if usage is not None else 0
    output_tokens = getattr(usage, "output_tokens", 0) if usage is not None else 0
    # dict-shaped fakes
    if isinstance(usage, dict):
        input_tokens = int(usage.get("input_tokens", 0))
        output_tokens = int(usage.get("output_tokens", 0))
    return {
        "input_tokens": int(input_tokens or 0),
        "output_tokens": int(output_tokens or 0),
        "model_id": model_id,
    }


def _parse_model_output(raw: str) -> NormalizerResult | None:
    """Parse the model's JSON text into a NormalizerResult.

    Returns None if the payload is malformed — caller converts to a
    `NORMALIZER_MALFORMED` refusal.
    """
    raw = raw.strip()
    if not raw:
        return None
    # Tolerate fenced code blocks ("```json\n{...}\n```") just in case,
    # but don't bend over backwards — Haiku follows "JSON only" reliably.
    if raw.startswith("```"):
        raw = raw.strip("`")
        if raw.startswith("json"):
            raw = raw[4:]
        raw = raw.strip()

    try:
        payload = json.loads(raw)
    except json.JSONDecodeError:
        return None
    if not isinstance(payload, dict):
        return None

    action = payload.get("action")
    if action == "refuse":
        reason_str = payload.get("reason")
        if reason_str == RefusalReason.OUT_OF_MEDICAL_SCOPE.value:
            return NormalizerRefusal(RefusalReason.OUT_OF_MEDICAL_SCOPE)
        if reason_str == RefusalReason.PATIENT_SPECIFIC_REQUEST.value:
            return NormalizerRefusal(RefusalReason.PATIENT_SPECIFIC_REQUEST)
        return None

    if action != "normalize":
        return None

    if "structured_query" not in payload:
        return None

    try:
        return NormalizedQuery(
            structured_query=payload["structured_query"],
            condition_tags=payload.get("condition_tags", []),
            intent=payload.get("intent", "other"),
            patient_context=payload.get("patient_context", "unspecified"),
            keywords_id=payload.get("keywords_id", []),
            keywords_en=payload.get("keywords_en", []),
            red_flags=payload.get("red_flags", []),
        )
    except ValidationError:
        return None


class HaikuNormalizer:
    """Normalizer backed by Claude Haiku 4.5.

    One shot per call. No retries. Output is a `NormalizedQuery` or a
    `NormalizerRefusal`. Transport errors from the Anthropic client
    propagate.

    Tests inject a fake client via `anthropic_client=...`. In production
    the client is built lazily from `api_key` via `_build_client`.
    """

    def __init__(
        self,
        *,
        api_key: str | None = None,
        model_id: str = DEFAULT_MODEL_ID,
        anthropic_client: _AnthropicLike | None = None,
        system_prompt: str | None = None,
    ) -> None:
        if anthropic_client is None and not api_key:
            raise ValueError(
                "HaikuNormalizer requires either an `anthropic_client` or an `api_key`."
            )
        self.model_id = model_id
        self._client: _AnthropicLike = (
            anthropic_client if anthropic_client is not None else _build_client(api_key or "")
        )
        self._system_prompt = system_prompt if system_prompt is not None else _load_system_prompt()
        self.last_usage: dict[str, Any] | None = None

    async def run(self, state: QueryState) -> NormalizerResult:
        user_query = state.original_query
        started = time.perf_counter()

        # Pre-LLM fast-path: unambiguously non-medical queries skip the
        # Haiku round-trip entirely and return a refusal in ~0ms. Only
        # fires when we're confident — see _is_obviously_non_medical.
        if _is_obviously_non_medical(user_query):
            log.info(
                "normalizer.heuristic_refuse",
                reason="out_of_medical_scope",
                input_length=len(user_query),
            )
            self.last_usage = {"input_tokens": 0, "output_tokens": 0, "thinking_tokens": 0}
            return NormalizerRefusal(RefusalReason.OUT_OF_MEDICAL_SCOPE)

        # Anthropic's Python SDK `messages.create` is synchronous. We run
        # inside an async agent Protocol but do not await — the SDK call
        # blocks the loop briefly. Orchestrator treats Normalizer as a
        # short, single-shot call so this is acceptable for the hackathon
        # build. If latency becomes an issue, swap for `AsyncAnthropic`.
        response = self._client.messages.create(
            model=self.model_id,
            max_tokens=MAX_OUTPUT_TOKENS,
            system=self._system_prompt,
            messages=[{"role": "user", "content": user_query}],
        )

        self.last_usage = _parse_usage(response, self.model_id)
        latency_ms = int((time.perf_counter() - started) * 1000)

        raw_text = _extract_text(response)
        parsed = _parse_model_output(raw_text)

        if parsed is None:
            log.warning(
                "normalizer.malformed",
                input_length=len(user_query),
                latency_ms=latency_ms,
                tokens_in=self.last_usage["input_tokens"],
                tokens_out=self.last_usage["output_tokens"],
                raw_preview=raw_text[:200],
            )
            return NormalizerRefusal(RefusalReason.NORMALIZER_MALFORMED)

        action = (
            "refuse" if isinstance(parsed, NormalizerRefusal) else "normalize"
        )
        log.info(
            "normalizer.call",
            input_length=len(user_query),
            latency_ms=latency_ms,
            action=action,
            tokens_in=self.last_usage["input_tokens"],
            tokens_out=self.last_usage["output_tokens"],
        )
        return parsed
