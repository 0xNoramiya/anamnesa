"""Verifier agent — Opus 4.7 with 1M-context.

Re-reads each cited section, classifies every claim as
`supported | partial | unsupported`, and attaches currency flags. Verifier
never rewrites the draft — it judges.

Mechanism: Anthropic tool-use loop. Three tools are exposed to Claude:

  - `get_full_section`      — fetch surrounding text if the retriever supports it
  - `check_supersession`    — check if a newer guideline exists for a doc_id
  - `submit_verification`   — terminal tool; its input IS the `VerificationResult`

Design choices (non-obvious, documented inline):

1. Fail-closed. If Claude ends the turn without submitting, the loop cap
   exceeds, or the submit input is malformed, we return an all-`unsupported`
   VerificationResult with synthetic feedback. The orchestrator's verifier-
   retry-then-refuse path fires — CITATIONS_UNVERIFIABLE is the right
   terminal state for a verifier that can't ground anything.

2. Invariant auto-coercion. The spec requires `feedback_for_drafter` to be
   non-null iff any verification is `unsupported`. If Claude submits an
   unsupported claim without feedback, we synthesize one from the claim
   reasoning rather than fail hard — Claude is close enough, and a
   synthesized handoff is more useful than a refusal.

3. Helper-tool fallbacks. `get_full_section` and `check_supersession` are
   dispatched to the injected `Retriever` only if the retriever exposes
   the relevant method. Otherwise we return a sentinel payload so Claude
   can continue without a crash (`LocalRetriever` in production exposes
   both; the test `FakeRetriever` does not).

Transport errors propagate per the "Errors loud, not swallowed" rule.
"""

from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Any, Protocol

import structlog
from pydantic import ValidationError

from agents.base import Retriever
from core.state import (
    ClaimVerification,
    CurrencyFlag,
    DraftAnswer,
    QueryState,
    VerificationResult,
)

log = structlog.get_logger("anamnesa.agents.verifier")

DEFAULT_MODEL_ID = "claude-opus-4-7"
MAX_OUTPUT_TOKENS = 16_000  # includes adaptive-thinking tokens on Opus 4.7
DEFAULT_THINKING_BUDGET = 12_000
MAX_LOOP_ITERATIONS = 8
PROMPT_PATH = Path(__file__).parent / "prompts" / "verifier.md"


class VerifierPromptError(RuntimeError):
    """Raised if the system prompt file is missing or unreadable."""


def _load_system_prompt() -> str:
    try:
        return PROMPT_PATH.read_text(encoding="utf-8")
    except OSError as exc:  # pragma: no cover - would fail all tests
        raise VerifierPromptError(f"Verifier prompt not found at {PROMPT_PATH}") from exc


class _AnthropicLike(Protocol):
    """Minimal shape of the Anthropic SDK client we depend on.

    Same seam as `HaikuNormalizer` / `OpusDrafter`: tests inject a fake,
    production builds a real `anthropic.Anthropic` via `_build_client`.
    """

    messages: Any


def _build_client(api_key: str) -> _AnthropicLike:
    """Factory for the real Anthropic client. Local import to avoid
    loading the SDK when tests inject a fake."""
    from anthropic import Anthropic

    return Anthropic(api_key=api_key)


# ---------------------------------------------------------------------------
# Tool schemas
# ---------------------------------------------------------------------------


_GET_FULL_SECTION_SCHEMA: dict[str, Any] = {
    "type": "object",
    "properties": {
        "doc_id": {"type": "string"},
        "section_path": {"type": "string"},
    },
    "required": ["doc_id", "section_path"],
}


_CHECK_SUPERSESSION_SCHEMA: dict[str, Any] = {
    "type": "object",
    "properties": {
        "doc_id": {"type": "string"},
    },
    "required": ["doc_id"],
}


_VERIFICATION_ITEM_SCHEMA: dict[str, Any] = {
    "type": "object",
    "properties": {
        "claim_id": {"type": "string"},
        "status": {
            "type": "string",
            "enum": ["supported", "partial", "unsupported"],
        },
        "reasoning": {"type": "string"},
    },
    "required": ["claim_id", "status", "reasoning"],
}


_CURRENCY_FLAG_SCHEMA: dict[str, Any] = {
    "type": "object",
    "properties": {
        "citation_key": {"type": "string"},
        "status": {
            "type": "string",
            "enum": ["current", "superseded", "aging", "unknown", "withdrawn"],
        },
        "source_year": {"type": "integer"},
        "superseding_doc_id": {"type": ["string", "null"]},
        "note_id": {"type": ["string", "null"]},
    },
    "required": ["citation_key", "status", "source_year"],
}


_SUBMIT_VERIFICATION_SCHEMA: dict[str, Any] = {
    "type": "object",
    "description": (
        "Terminal tool. Submit one VerificationResult. Invariant: "
        "`feedback_for_drafter` is non-null iff at least one verification "
        "has status 'unsupported'. `currency_flags` has exactly one entry "
        "per unique citation_key in the draft."
    ),
    "properties": {
        "verifications": {
            "type": "array",
            "items": _VERIFICATION_ITEM_SCHEMA,
        },
        "currency_flags": {
            "type": "array",
            "items": _CURRENCY_FLAG_SCHEMA,
        },
        "feedback_for_drafter": {"type": ["string", "null"]},
    },
    "required": ["verifications", "currency_flags"],
}


def _tool_specs() -> list[dict[str, Any]]:
    return [
        {
            "name": "get_full_section",
            "description": (
                "Fetch the full section around a cited chunk. Use liberally "
                "when a chunk is short or ambiguous — Verifier runs on 1M "
                "context and can afford the tokens. Returns the section "
                "text (or an error structure if unavailable)."
            ),
            "input_schema": _GET_FULL_SECTION_SCHEMA,
        },
        {
            "name": "check_supersession",
            "description": (
                "Check if a newer guideline supersedes this doc_id on the "
                "same topic. Call for every unique doc_id in the draft's "
                "citations. Returns "
                "{status, superseding_doc_id, source_year}."
            ),
            "input_schema": _CHECK_SUPERSESSION_SCHEMA,
        },
        {
            "name": "submit_verification",
            "description": (
                "Terminal tool — call EXACTLY ONCE with the final "
                "VerificationResult. See input_schema."
            ),
            "input_schema": _SUBMIT_VERIFICATION_SCHEMA,
        },
    ]


# ---------------------------------------------------------------------------
# Serialization helpers
# ---------------------------------------------------------------------------


def _render_retrieval_history(state: QueryState) -> str:
    blocks: list[str] = []
    for attempt in state.retrieval_attempts:
        for chunk in attempt.chunks:
            key = f"{chunk.doc_id}:p{chunk.page}:{chunk.section_slug}"
            body = " ".join(chunk.text.split())
            blocks.append(
                f'<chunk id="{key}" year="{chunk.year}" '
                f'source="{chunk.source_type}" attempt="{attempt.attempt_num}">\n'
                f"{body}\n"
                "</chunk>"
            )
    if not blocks:
        return "<retrieval_history>(no chunks retrieved)</retrieval_history>"
    return "<retrieval_history>\n" + "\n".join(blocks) + "\n</retrieval_history>"


def _render_draft(draft: DraftAnswer) -> str:
    content = draft.content
    claim_lines = "\n".join(
        f'- id={c.claim_id} text="{c.text}" cites={list(c.citation_keys)}'
        for c in draft.claims
    )
    citation_blocks = "\n".join(
        (
            f'<citation key="{c.key}" doc_id="{c.doc_id}" '
            f'page="{c.page}" section="{c.section_slug}">\n'
            f"{c.chunk_text}\n"
            "</citation>"
        )
        for c in draft.citations
    )
    return (
        "<draft>\n"
        "<content>\n"
        f"{content}\n"
        "</content>\n\n"
        "<claims>\n"
        f"{claim_lines}\n"
        "</claims>\n"
        "</draft>\n\n"
        "<citations_in_draft>\n"
        f"{citation_blocks}\n"
        "</citations_in_draft>"
    )


def _build_initial_user_message(state: QueryState) -> str:
    """Render the Verifier's initial user message.

    Cost-shape: we pass only `<draft>` + `<citations_in_draft>` (cited chunks
    verbatim). The fuller `<retrieval_history>` (all retrieved chunks the
    Drafter saw) is omitted to keep Verifier input ~30% leaner. If the
    Verifier wants more context, it can call `get_full_section` on demand;
    a retrieval-history block fed upfront burns ~12K tokens per iteration
    for information that is rarely used to catch "missed better citation"
    errors in practice.
    """
    assert state.draft_answer is not None
    parts = [
        _render_draft(state.draft_answer),
        (
            "Judge each claim against the cited text. Call "
            "`get_full_section` (for broader context) and `check_supersession` "
            "(for currency) as needed, then submit your final verdict via "
            "`submit_verification`. You judge; you do NOT rewrite."
        ),
    ]
    return "\n\n".join(parts)


# ---------------------------------------------------------------------------
# Response parsing helpers
# ---------------------------------------------------------------------------


def _extract_usage(response: Any) -> tuple[int, int, int]:
    """Pull (input, output, thinking) token counts from a Messages response."""
    usage = getattr(response, "usage", None)
    if isinstance(usage, dict):
        return (
            int(usage.get("input_tokens", 0) or 0),
            int(usage.get("output_tokens", 0) or 0),
            int(usage.get("thinking_tokens", 0) or 0),
        )
    if usage is None:
        return (0, 0, 0)
    input_tokens = int(getattr(usage, "input_tokens", 0) or 0)
    output_tokens = int(getattr(usage, "output_tokens", 0) or 0)
    thinking_tokens = int(getattr(usage, "thinking_tokens", 0) or 0)
    return (input_tokens, output_tokens, thinking_tokens)


def _iter_content_blocks(response: Any) -> list[Any]:
    content = getattr(response, "content", None) or []
    return list(content)


def _block_attr(block: Any, name: str, default: Any = None) -> Any:
    if isinstance(block, dict):
        return block.get(name, default)
    return getattr(block, name, default)


# ---------------------------------------------------------------------------
# Fail-closed helper
# ---------------------------------------------------------------------------


def _all_unsupported_verification(
    draft: DraftAnswer | None,
    reasoning: str,
) -> VerificationResult:
    """Build an all-`unsupported` VerificationResult.

    Used when the verifier fails to produce usable output — loop cap
    exceeded, stop_reason=end_turn without submission, malformed input,
    etc. The orchestrator's verifier-retry-then-refuse path fires on this
    because every claim is unsupported.
    """
    if draft is None:
        # Shouldn't happen in the orchestrator's flow, but fail closed.
        return VerificationResult(
            verifications=[],
            currency_flags=[],
            feedback_for_drafter="verifier response malformed; no grounding analysis available",
        )
    verifications = [
        ClaimVerification(
            claim_id=c.claim_id,
            status="unsupported",
            reasoning="verifier failed to submit",
        )
        for c in draft.claims
    ]
    return VerificationResult(
        verifications=verifications,
        currency_flags=[],
        feedback_for_drafter=(
            f"verifier response malformed; no grounding analysis available ({reasoning})"
        ),
    )


# ---------------------------------------------------------------------------
# Parse & coerce submit_verification input
# ---------------------------------------------------------------------------


def _synthesize_feedback(verifications: list[ClaimVerification]) -> str:
    """Compose a feedback string from unsupported claims' reasoning.

    Used when Claude submits unsupported claims but forgets
    `feedback_for_drafter`. Keeps it actionable by naming each claim_id.
    """
    lines = [
        f"{v.claim_id}: {v.reasoning}"
        for v in verifications
        if v.status == "unsupported"
    ]
    if not lines:
        # Defensive: caller only invokes when at least one unsupported exists.
        return "One or more claims were unsupported; please revise citations."
    return "Unsupported claim(s): " + " | ".join(lines)


def _parse_submit_input(
    tool_input: dict[str, Any],
    draft: DraftAnswer | None,
) -> VerificationResult | None:
    """Parse a `submit_verification` tool input into a VerificationResult.

    Returns None if the input cannot be coerced — caller falls back to
    `_all_unsupported_verification`. Applies the invariant-coercion rule:
    if any claim is `unsupported` and feedback is missing, synthesize one.
    """
    try:
        result = VerificationResult.model_validate(tool_input)
    except ValidationError:
        return None
    except TypeError:
        return None

    if result.has_unsupported and not result.feedback_for_drafter:
        synthesized = _synthesize_feedback(list(result.verifications))
        # model_config is frozen; round-trip through model_validate.
        patched = result.model_dump()
        patched["feedback_for_drafter"] = synthesized
        try:
            result = VerificationResult.model_validate(patched)
        except ValidationError:
            # Extremely unlikely — original was valid; giving up here
            # would orphan a correct judgement. Fall back to fail-closed.
            return _all_unsupported_verification(
                draft, "invariant coercion failed"
            )
        log.info(
            "verifier.feedback_synthesized",
            unsupported=sum(
                1 for v in result.verifications if v.status == "unsupported"
            ),
        )
    elif not result.has_unsupported and result.feedback_for_drafter:
        # Inverse invariant violation: feedback with no unsupported claims.
        # Drop the feedback — orchestrator keys off `has_unsupported`, but
        # keeping stray feedback is confusing in traces.
        patched = result.model_dump()
        patched["feedback_for_drafter"] = None
        try:
            result = VerificationResult.model_validate(patched)
        except ValidationError:  # pragma: no cover - defensive
            pass
    return result


# ---------------------------------------------------------------------------
# Tool dispatch
# ---------------------------------------------------------------------------


def _dispatch_get_full_section(
    retriever: Any, tool_input: dict[str, Any]
) -> dict[str, Any]:
    fn = getattr(retriever, "get_full_section", None)
    if not callable(fn):
        return {"error": "not_available"}
    try:
        result = fn(
            str(tool_input.get("doc_id", "")),
            str(tool_input.get("section_path", "")),
        )
    except Exception as exc:  # surface reason to Claude instead of crashing the loop
        return {"error": f"get_full_section failed: {exc}"}
    if isinstance(result, dict):
        return result
    return {"section_text": str(result)}


def _dispatch_check_supersession(
    retriever: Any, tool_input: dict[str, Any]
) -> dict[str, Any]:
    fn = getattr(retriever, "check_supersession", None)
    if not callable(fn):
        return {
            "status": "unknown",
            "superseding_doc_id": None,
            "source_year": 0,
        }
    try:
        result = fn(str(tool_input.get("doc_id", "")))
    except Exception as exc:  # surface reason to Claude instead of crashing the loop
        return {"error": f"check_supersession failed: {exc}"}
    if isinstance(result, dict):
        return result
    return {"status": "unknown", "superseding_doc_id": None, "source_year": 0}


# ---------------------------------------------------------------------------
# OpusVerifier
# ---------------------------------------------------------------------------


class OpusVerifier:
    """Verifier backed by Claude Opus 4.7 (1M ctx).

    Runs an Anthropic tool-use loop over up to `MAX_LOOP_ITERATIONS`
    iterations. Returns a `VerificationResult`. Fails closed (all claims
    `unsupported`) if Claude cannot produce a usable verdict within the
    loop budget.

    Constructor accepts either an `anthropic_client` (for tests) or an
    `api_key` (production); the latter triggers a lazy import of the
    Anthropic SDK.
    """

    def __init__(
        self,
        *,
        retriever: Retriever,
        api_key: str | None = None,
        model_id: str = DEFAULT_MODEL_ID,
        anthropic_client: _AnthropicLike | None = None,
        system_prompt: str | None = None,
        thinking_budget: int = DEFAULT_THINKING_BUDGET,
        max_output_tokens: int = MAX_OUTPUT_TOKENS,
    ) -> None:
        if anthropic_client is None and not api_key:
            raise ValueError(
                "OpusVerifier requires either an `anthropic_client` or an `api_key`."
            )
        self.retriever = retriever
        self.model_id = model_id
        self._client: _AnthropicLike = (
            anthropic_client
            if anthropic_client is not None
            else _build_client(api_key or "")
        )
        self._system_prompt = (
            system_prompt if system_prompt is not None else _load_system_prompt()
        )
        self.thinking_budget = thinking_budget
        self.max_output_tokens = max_output_tokens
        self.last_usage: dict[str, Any] | None = None

    # ---------------------------------------------------------------- run

    async def run(self, state: QueryState) -> VerificationResult:
        draft = state.draft_answer
        if draft is None:
            # Orchestrator guards this, but fail loud rather than index None.
            log.warning("verifier.missing_draft", query_id=state.query_id)
            return _all_unsupported_verification(None, "no draft to verify")

        user_prompt = _build_initial_user_message(state)
        messages: list[dict[str, Any]] = [{"role": "user", "content": user_prompt}]

        tools = _tool_specs()
        # Cache-shape: system prompt is static; tools render in front of it in
        # the prefix. Marking the system block for caching covers both and
        # gives ~10x cost reduction on cache reads across queries within the
        # 5-minute TTL. Min cacheable prefix on Opus 4.7 is 4096 tokens; our
        # tools + system easily clear that threshold.
        system_blocks = [
            {
                "type": "text",
                "text": self._system_prompt,
                "cache_control": {"type": "ephemeral"},
            }
        ]
        kwargs_base: dict[str, Any] = {
            "model": self.model_id,
            "max_tokens": self.max_output_tokens,
            "system": system_blocks,
            "tools": tools,
        }
        # Opus 4.7: adaptive thinking only. See drafter.py for rationale.
        if self.thinking_budget > 0:
            kwargs_base["thinking"] = {"type": "adaptive"}
            kwargs_base["output_config"] = {"effort": "xhigh"}

        usage_totals = {"input_tokens": 0, "output_tokens": 0, "thinking_tokens": 0}
        started = time.perf_counter()
        decision: VerificationResult | None = None

        iterations = 0
        while iterations < MAX_LOOP_ITERATIONS:
            iterations += 1

            response = self._client.messages.create(
                messages=list(messages),
                **kwargs_base,
            )

            in_tok, out_tok, think_tok = _extract_usage(response)
            usage_totals["input_tokens"] += in_tok
            usage_totals["output_tokens"] += out_tok
            usage_totals["thinking_tokens"] += think_tok

            stop_reason = getattr(response, "stop_reason", None)
            if isinstance(response, dict):
                stop_reason = response.get("stop_reason", stop_reason)

            content_blocks = _iter_content_blocks(response)

            if stop_reason != "tool_use":
                # Verifier bailed without submitting — fail closed.
                log.warning(
                    "verifier.no_tool_call",
                    iteration=iterations,
                    stop_reason=stop_reason,
                    query_id=state.query_id,
                )
                decision = _all_unsupported_verification(
                    draft, "verifier did not submit"
                )
                break

            # Append assistant turn verbatim so tool_use_id refs line up.
            messages.append({"role": "assistant", "content": content_blocks})

            tool_results: list[dict[str, Any]] = []
            submitted = False

            for block in content_blocks:
                if _block_attr(block, "type") != "tool_use":
                    continue
                tool_name = _block_attr(block, "name")
                tool_use_id = _block_attr(block, "id")
                tool_input = _block_attr(block, "input") or {}
                if not isinstance(tool_input, dict):
                    tool_input = {}

                if tool_name == "submit_verification":
                    parsed = _parse_submit_input(tool_input, draft)
                    if parsed is None:
                        log.warning(
                            "verifier.submit_malformed",
                            iteration=iterations,
                            query_id=state.query_id,
                        )
                        decision = _all_unsupported_verification(
                            draft, "verifier input validation failed"
                        )
                    else:
                        decision = parsed
                    submitted = True
                    log.info(
                        "tool_dispatched",
                        tool="submit_verification",
                        iteration=iterations,
                        has_unsupported=(
                            decision.has_unsupported if decision else None
                        ),
                    )
                    break  # stop processing further blocks

                if tool_name == "get_full_section":
                    result_payload = _dispatch_get_full_section(
                        self.retriever, tool_input
                    )
                    log.info(
                        "tool_dispatched",
                        tool="get_full_section",
                        iteration=iterations,
                        doc_id=tool_input.get("doc_id"),
                    )
                elif tool_name == "check_supersession":
                    result_payload = _dispatch_check_supersession(
                        self.retriever, tool_input
                    )
                    log.info(
                        "tool_dispatched",
                        tool="check_supersession",
                        iteration=iterations,
                        doc_id=tool_input.get("doc_id"),
                    )
                else:
                    log.warning(
                        "verifier.unknown_tool",
                        iteration=iterations,
                        tool=tool_name,
                    )
                    result_payload = {"error": f"unknown tool: {tool_name!r}"}

                tool_results.append(
                    {
                        "type": "tool_result",
                        "tool_use_id": tool_use_id,
                        "content": json.dumps(result_payload, ensure_ascii=False),
                    }
                )

            if submitted:
                break

            if not tool_results:
                # stop_reason was tool_use but no usable tool_use blocks.
                log.warning(
                    "verifier.empty_tool_use",
                    iteration=iterations,
                    query_id=state.query_id,
                )
                decision = _all_unsupported_verification(
                    draft, "empty tool-use response"
                )
                break

            messages.append({"role": "user", "content": tool_results})

        if decision is None:
            log.warning(
                "verifier.loop_cap_exceeded",
                iterations=iterations,
                query_id=state.query_id,
            )
            decision = _all_unsupported_verification(
                draft, "loop cap exceeded"
            )

        latency_ms = int((time.perf_counter() - started) * 1000)
        self.last_usage = {
            "input_tokens": usage_totals["input_tokens"],
            "output_tokens": usage_totals["output_tokens"],
            "thinking_tokens": usage_totals["thinking_tokens"],
            "model_id": self.model_id,
            "iterations": iterations,
        }

        unsupported_count = sum(
            1 for v in decision.verifications if v.status == "unsupported"
        )
        supported_count = sum(
            1 for v in decision.verifications if v.status == "supported"
        )
        partial_count = sum(
            1 for v in decision.verifications if v.status == "partial"
        )
        flag_statuses = sorted({f.status for f in decision.currency_flags})
        log.info(
            "verifier.judged",
            iterations=iterations,
            latency_ms=latency_ms,
            tokens_in=usage_totals["input_tokens"],
            tokens_out=usage_totals["output_tokens"],
            tokens_thinking=usage_totals["thinking_tokens"],
            supported=supported_count,
            partial=partial_count,
            unsupported=unsupported_count,
            currency_flag_statuses=flag_statuses,
            query_id=state.query_id,
        )
        return decision


__all__ = ["CurrencyFlag", "OpusVerifier", "VerifierPromptError"]
