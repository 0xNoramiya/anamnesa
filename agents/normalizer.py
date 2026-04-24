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


# Pre-LLM heuristic: skip the Haiku round-trip for unambiguously non-clinical
# queries. Conservative — a clinical query mis-classified as non-medical is
# much worse than a non-medical one that goes through to Haiku. Only
# short-circuits when a non-medical phrase matches AND zero clinical safety
# tokens appear.

_NON_MEDICAL_PHRASES: tuple[str, ...] = (
    "apa kabar", "selamat pagi", "selamat siang", "selamat sore",
    "selamat malam", "terima kasih", "hi ", "hello ", "halo ",
    "tell me a joke", "ceritakan lelucon", "tolong buat lelucon",
    # "resep" alone is clinical ("resep asam mefenamat"), so only match it
    # bound to a specific dish.
    "resep nasi", "resep masakan", "resep kue", "resep soto",
    "resep ayam", "resep sambal", "resep mie", "resep rendang",
    "cuaca ", "suhu jakarta", "suhu bandung", "ibukota ",
    "capital of ", "what is the weather",
    "write code", "write a function", "python function", "sql query",
    "regex untuk", "tulis kode", "buat script", "javascript code",
    "harga emas", "harga saham", "kurs dollar", "rate usd",
    "tips jualan", "cara dagang",
    "presiden sekarang", "berita terbaru", "news today",
    "berapa 1+1", "berapa 2+2", "what is 2+2", "1 plus 1",
)

# If any of these appears the query goes through to Haiku no matter what —
# protects against false positives like "resep asam mefenamat".
_CLINICAL_SAFETY_TOKENS: frozenset[str] = frozenset({
    "dbd", "demam", "dengue", "tb", "tuberkulosis", "hipertensi",
    "diabetes", "dm", "stroke", "infark", "asma", "ppok", "sepsis",
    "pneumonia", "ispa", "gagal", "jantung", "ginjal", "hepar",
    "covid", "hiv", "malaria", "tifoid", "cacar", "campak",
    "paru", "hati", "lambung", "usus", "otak",
    "tulang", "sendi", "mata", "telinga", "hidung", "kulit",
    "amoksisilin", "parasetamol", "ibuprofen", "metformin",
    "insulin", "oat", "rhze", "antibiotik", "analgetik", "nsaid",
    "kortikosteroid", "furosemid", "ramipril", "amlodipin",
    "mg/kg", "mg/kgbb", "mcg", "unit/kg", "dosis",
    "vtp", "rjp", "cpr", "iv", "im", "sc", "po", "pct",
    "pasien", "anak", "bayi", "balita", "neonatus", "ibu hamil",
    "hamil", "lansia", "geriatri",
    "tata laksana", "tatalaksana", "diagnosis",
    "rujukan", "tanda", "gejala", "sindrom", "keluhan",
})


def _is_obviously_non_medical(query: str) -> bool:
    """Return True when the query is almost certainly not clinical."""
    text = query.lower().strip()
    if not text:
        return False
    if text.isnumeric():
        return True
    if not any(phrase in text for phrase in _NON_MEDICAL_PHRASES):
        return False
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
    """Minimal shape of the Anthropic SDK client used by this agent."""

    messages: Any


def _build_client(api_key: str) -> _AnthropicLike:
    from anthropic import Anthropic

    return Anthropic(api_key=api_key)


def _extract_text(response: Any) -> str:
    """Pick the first text block out of a Messages API response.

    Returns empty string on unexpected shapes; caller treats as malformed.
    """
    content = getattr(response, "content", None)
    if not content:
        return ""
    for block in content:
        text = getattr(block, "text", None)
        if isinstance(text, str):
            return text
        if isinstance(block, dict) and block.get("type") == "text":
            return str(block.get("text", ""))
    return ""


def _parse_usage(response: Any, model_id: str) -> dict[str, Any]:
    usage = getattr(response, "usage", None)
    input_tokens = getattr(usage, "input_tokens", 0) if usage is not None else 0
    output_tokens = getattr(usage, "output_tokens", 0) if usage is not None else 0
    if isinstance(usage, dict):
        input_tokens = int(usage.get("input_tokens", 0))
        output_tokens = int(usage.get("output_tokens", 0))
    return {
        "input_tokens": int(input_tokens or 0),
        "output_tokens": int(output_tokens or 0),
        "model_id": model_id,
    }


def _extract_first_json_object(text: str) -> str | None:
    """Return the first balanced {...} block in `text`, or None.

    String-aware so braces inside quoted strings don't false-match.
    """
    depth = 0
    start = -1
    in_string = False
    escape = False
    for i, ch in enumerate(text):
        if in_string:
            if escape:
                escape = False
            elif ch == "\\":
                escape = True
            elif ch == '"':
                in_string = False
            continue
        if ch == '"':
            in_string = True
            continue
        if ch == "{":
            if depth == 0:
                start = i
            depth += 1
        elif ch == "}":
            if depth == 0:
                continue
            depth -= 1
            if depth == 0 and start >= 0:
                return text[start : i + 1]
    return None


def _parse_model_output(raw: str) -> NormalizerResult | None:
    """Parse the model's JSON text into a NormalizerResult.

    Returns None if the payload is malformed — caller converts to
    `NORMALIZER_MALFORMED`.
    """
    raw = raw.strip()
    if not raw:
        return None
    # Tolerate fenced code blocks. Haiku follows "JSON only" reliably but
    # occasionally wraps anyway.
    if raw.startswith("```"):
        raw = raw.strip("`")
        if raw.startswith("json"):
            raw = raw[4:]
        raw = raw.strip()

    payload: Any
    try:
        payload = json.loads(raw)
    except json.JSONDecodeError:
        # Fallback when Haiku narrates before emitting JSON.
        extracted = _extract_first_json_object(raw)
        if extracted is None:
            return None
        try:
            payload = json.loads(extracted)
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

    One shot per call, no retries. Output is `NormalizedQuery` or
    `NormalizerRefusal`. Transport errors propagate. Tests inject a fake
    client via `anthropic_client=`.
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

    async def run(
        self,
        state: QueryState,
        *,
        prior_turn: dict[str, str] | None = None,
    ) -> NormalizerResult:
        user_query = state.original_query
        started = time.perf_counter()

        # Skip Haiku for unambiguously non-medical queries. Skipped on
        # follow-ups — "dan kalau anak?" looks non-medical in isolation.
        if prior_turn is None and _is_obviously_non_medical(user_query):
            log.info(
                "normalizer.heuristic_refuse",
                reason="out_of_medical_scope",
                input_length=len(user_query),
            )
            self.last_usage = {"input_tokens": 0, "output_tokens": 0, "thinking_tokens": 0}
            return NormalizerRefusal(RefusalReason.OUT_OF_MEDICAL_SCOPE)

        user_message = _build_user_message(user_query, prior_turn)

        # SDK `messages.create` is synchronous; blocks the loop briefly.
        # Acceptable because Normalizer is short and single-shot.
        response = self._client.messages.create(
            model=self.model_id,
            max_tokens=MAX_OUTPUT_TOKENS,
            system=self._system_prompt,
            messages=[{"role": "user", "content": user_message}],
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
            multi_turn=prior_turn is not None,
            tokens_in=self.last_usage["input_tokens"],
            tokens_out=self.last_usage["output_tokens"],
        )
        return parsed


def _build_user_message(
    user_query: str, prior_turn: dict[str, str] | None
) -> str:
    """Assemble the user-side message for Haiku.

    Multi-turn: inject prior Q/A and ask Haiku to condense the follow-up into a
    standalone clinical query, preserving population / setting hints from the
    prior answer.
    """
    if prior_turn is None:
        return user_query
    prior_q = prior_turn.get("query", "").strip()
    prior_a = prior_turn.get("answer", "").strip()
    if not prior_q or not prior_a:
        return user_query
    return (
        "Ini adalah pertanyaan lanjutan dalam percakapan klinis. Gunakan "
        "konteks pertanyaan + jawaban sebelumnya untuk memahami maksud "
        "pertanyaan lanjutan, lalu hasilkan `structured_query` sebagai "
        "kueri klinis yang BERDIRI SENDIRI (standalone) — sertakan topik, "
        "populasi pasien, dan konteks dari jawaban sebelumnya jika "
        "pertanyaan lanjutannya singkat atau elipsis.\n\n"
        "[Pertanyaan sebelumnya]\n"
        f"{prior_q}\n\n"
        "[Ringkasan jawaban sebelumnya]\n"
        f"{prior_a}\n\n"
        "[Pertanyaan lanjutan pengguna]\n"
        f"{user_query}"
    )
