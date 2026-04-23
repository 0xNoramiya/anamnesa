"""Drafter agent — Opus 4.7 with adaptive thinking.

Implements the Drafter described in CLAUDE.md > "Agent roster" > Drafter and
in `agents/prompts/drafter.md`.

Decision space (one of three terminal outcomes):
  - `answer`              — cited Bahasa draft, one citation per claim
  - `need_more_retrieval` — ask the orchestrator to search again
  - `refuse`              — corpus silent / out of scope / patient-specific

Mechanism: Anthropic tool-use loop. Four tools are exposed to Claude:

  - `search_guidelines`   — narrower retrieval via the injected `Retriever`
  - `get_full_section`    — fetch surrounding text if the retriever supports it
  - `submit_decision`     — terminal tool; its input IS the `DrafterResult`

Design choices (documented inline because they are non-obvious):

1. Intra-drafter `search_guidelines` calls are private. They go through the
   same `Retriever` protocol but do NOT mutate `state.retrieval_attempts`
   — the orchestrator manages `retrieval_attempts` as the per-query budget
   counter. The drafter's "please re-retrieve" request to the orchestrator
   is the `need_more_retrieval` decision, not these intra-loop calls.

2. If Claude ends the turn without ever calling `submit_decision` we return
   `DrafterRefuse(reason=RefusalReason.CITATIONS_UNVERIFIABLE)`. There is
   no refusal enum for "drafter produced malformed output". The closest
   semantic match is `citations_unverifiable` — we could not ground what
   the drafter did (or did not) produce; the verifier-gate failure lane
   is the right terminal state.

3. Hard cap at 8 iterations. If Claude keeps calling helper tools without
   ever submitting, we refuse with `citations_unverifiable` and log.

Transport errors propagate per the "Errors loud, not swallowed" rule.
"""

from __future__ import annotations

import asyncio
import json
import time
from pathlib import Path
from typing import Any, Protocol

import structlog
from pydantic import ValidationError

from agents.base import Retriever
from core.refusals import RefusalReason
from core.state import (
    Chunk,
    Citation,
    Claim,
    DraftAnswer,
    DrafterAnswerDecision,
    DrafterNeedMoreRetrieval,
    DrafterRefuse,
    DrafterResult,
    NormalizedQuery,
    QueryState,
    RetrievalFilters,
)
from core.trace import trace

log = structlog.get_logger("anamnesa.agents.drafter")

DEFAULT_MODEL_ID = "claude-opus-4-7"
MAX_OUTPUT_TOKENS = 16_000  # includes adaptive-thinking tokens on Opus 4.7
# Drafter now defaults to thinking_budget=0 because adaptive thinking
# batches all output through the tool call → no text streaming, which
# defeats the live-answer UX. Rollback to 8000 is a single-arg change
# if future benchmarks show quality drift.
DEFAULT_THINKING_BUDGET = 0
DEFAULT_EFFORT = "xhigh"  # unused when thinking_budget=0; kept for callers
MAX_LOOP_ITERATIONS = 8
PROMPT_PATH = Path(__file__).parent / "prompts" / "drafter.md"

# Refusal reasons the Drafter is allowed to emit. Anything else in the
# `refuse` branch is treated as malformed and collapsed to
# CITATIONS_UNVERIFIABLE (see module docstring, point 2).
_DRAFTER_REFUSAL_REASONS: frozenset[str] = frozenset(
    {
        RefusalReason.CORPUS_SILENT.value,
        RefusalReason.ALL_SUPERSEDED_NO_CURRENT.value,
        RefusalReason.PATIENT_SPECIFIC_REQUEST.value,
        RefusalReason.OUT_OF_MEDICAL_SCOPE.value,
    }
)


class DrafterPromptError(RuntimeError):
    """Raised if the system prompt file is missing or unreadable."""


def _load_system_prompt() -> str:
    try:
        return PROMPT_PATH.read_text(encoding="utf-8")
    except OSError as exc:  # pragma: no cover - would fail all tests
        raise DrafterPromptError(f"Drafter prompt not found at {PROMPT_PATH}") from exc


class _AnthropicLike(Protocol):
    """Minimal shape of the Anthropic SDK client we depend on.

    Same seam as `HaikuNormalizer`: tests inject a fake, production builds
    a real `anthropic.Anthropic` via `_build_client`.
    """

    messages: Any


def _build_client(api_key: str) -> _AnthropicLike:
    """Factory for the real Anthropic client. Local import to avoid
    loading the SDK when tests inject a fake."""
    from anthropic import Anthropic

    return Anthropic(api_key=api_key)


# ---------------------------------------------------------------------------
# Tool schemas (hand-written, kept compact; Claude handles loose schemas well)
# ---------------------------------------------------------------------------


_SEARCH_GUIDELINES_SCHEMA: dict[str, Any] = {
    "type": "object",
    "properties": {
        "query": {
            "type": "string",
            "description": "Short Bahasa / English query for hybrid retrieval.",
        },
        "filters": {
            "type": "object",
            "description": (
                "Optional RetrievalFilters. Keys: doc_ids, source_types, "
                "conditions, min_year, max_year, section_types, top_k."
            ),
            "properties": {
                "doc_ids": {"type": "array", "items": {"type": "string"}},
                "source_types": {"type": "array", "items": {"type": "string"}},
                "conditions": {"type": "array", "items": {"type": "string"}},
                "min_year": {"type": "integer"},
                "max_year": {"type": "integer"},
                "section_types": {"type": "array", "items": {"type": "string"}},
                "top_k": {"type": "integer"},
            },
        },
    },
    "required": ["query"],
}

_GET_FULL_SECTION_SCHEMA: dict[str, Any] = {
    "type": "object",
    "properties": {
        "doc_id": {"type": "string"},
        "section_path": {"type": "string"},
    },
    "required": ["doc_id", "section_path"],
}


_CITATION_SCHEMA: dict[str, Any] = {
    "type": "object",
    "properties": {
        "key": {"type": "string"},
        "doc_id": {"type": "string"},
        "page": {"type": "integer"},
        "section_slug": {"type": "string"},
        "chunk_text": {"type": "string"},
    },
    "required": ["key", "doc_id", "page", "section_slug", "chunk_text"],
}


_CLAIM_SCHEMA: dict[str, Any] = {
    "type": "object",
    "properties": {
        "claim_id": {"type": "string"},
        "text": {"type": "string"},
        "citation_keys": {"type": "array", "items": {"type": "string"}},
    },
    "required": ["claim_id", "text", "citation_keys"],
}


_ANSWER_SCHEMA: dict[str, Any] = {
    "type": "object",
    "description": (
        "Metadata for the answer you already wrote as a text block before "
        "this tool call. Do NOT include `content` — the server reads the "
        "prose from the streamed text block."
    ),
    "properties": {
        # `content` kept as an optional legacy field so older prompts /
        # rolling deployments still work; when provided, we prefer it
        # over the text-block buffer. See OpusDrafter.run().
        "content": {"type": "string"},
        "claims": {"type": "array", "items": _CLAIM_SCHEMA},
        "citations": {"type": "array", "items": _CITATION_SCHEMA},
    },
    "required": ["claims", "citations"],
}


_FILTER_HINTS_SCHEMA: dict[str, Any] = {
    "type": "object",
    "properties": {
        "doc_ids": {"type": "array", "items": {"type": "string"}},
        "source_types": {"type": "array", "items": {"type": "string"}},
        "conditions": {"type": "array", "items": {"type": "string"}},
        "min_year": {"type": "integer"},
        "max_year": {"type": "integer"},
        "section_types": {"type": "array", "items": {"type": "string"}},
        "top_k": {"type": "integer"},
    },
}


_SUBMIT_DECISION_SCHEMA: dict[str, Any] = {
    "type": "object",
    "description": (
        "Terminal tool. Submit exactly one decision. The shape of the input "
        "is discriminated on `decision`:\n"
        '  - "answer":             {"decision":"answer","answer":{...}}\n'
        '  - "need_more_retrieval":{"decision":"need_more_retrieval",'
        '"filter_hints":{...},"feedback":"..."}\n'
        '  - "refuse":             {"decision":"refuse","reason":"..."}\n'
        "Allowed refuse reasons: corpus_silent, all_superseded_no_current, "
        "patient_specific_request, out_of_medical_scope."
    ),
    "properties": {
        "decision": {
            "type": "string",
            "enum": ["answer", "need_more_retrieval", "refuse"],
        },
        "answer": _ANSWER_SCHEMA,
        "filter_hints": _FILTER_HINTS_SCHEMA,
        "feedback": {"type": "string"},
        "reason": {
            "type": "string",
            "enum": sorted(_DRAFTER_REFUSAL_REASONS),
        },
    },
    "required": ["decision"],
}


def _tool_specs() -> list[dict[str, Any]]:
    return [
        {
            "name": "search_guidelines",
            "description": (
                "Hybrid retrieval over the Indonesian clinical guideline corpus. "
                "Use to fetch additional chunks when the initial retrieval is "
                "a near-miss (wrong population, wrong section type, missing "
                "condition filter). Returns {chunks: [...]}."
            ),
            "input_schema": _SEARCH_GUIDELINES_SCHEMA,
        },
        {
            "name": "get_full_section",
            "description": (
                "Fetch the full section surrounding a chunk. Use when a chunk "
                "is short or ambiguous before committing to a claim. Returns "
                "the section text (or an error structure if unavailable)."
            ),
            "input_schema": _GET_FULL_SECTION_SCHEMA,
        },
        {
            "name": "submit_decision",
            "description": (
                "Terminal tool — call this EXACTLY ONCE with your final "
                "decision. See input_schema for the three shapes."
            ),
            "input_schema": _SUBMIT_DECISION_SCHEMA,
        },
    ]


# ---------------------------------------------------------------------------
# Serialization — compact, LLM-friendly prompt blocks
# ---------------------------------------------------------------------------


def _render_chunk(chunk: Chunk) -> str:
    key = f"{chunk.doc_id}:p{chunk.page}:{chunk.section_slug}"
    # Whitespace-normalize the text so the prompt stays compact.
    body = " ".join(chunk.text.split())
    return (
        f'<chunk id="{key}" year="{chunk.year}" source="{chunk.source_type}" '
        f'score="{chunk.score:.3f}">\n{body}\n</chunk>'
    )


def _render_chunks(chunks: list[Chunk]) -> str:
    if not chunks:
        return "<chunks>(empty — no results returned)</chunks>"
    return "<chunks>\n" + "\n".join(_render_chunk(c) for c in chunks) + "\n</chunks>"


def _render_normalized_query(nq: NormalizedQuery) -> str:
    return (
        "<normalized_query>\n"
        f"  structured_query: {nq.structured_query}\n"
        f"  intent: {nq.intent}\n"
        f"  patient_context: {nq.patient_context}\n"
        f"  condition_tags: {list(nq.condition_tags)}\n"
        f"  keywords_id: {list(nq.keywords_id)}\n"
        f"  keywords_en: {list(nq.keywords_en)}\n"
        f"  red_flags: {list(nq.red_flags)}\n"
        "</normalized_query>"
    )


def _build_initial_user_message(
    *,
    nq: NormalizedQuery,
    chunks: list[Chunk],
    verifier_feedback: str | None,
) -> str:
    parts: list[str] = []
    if verifier_feedback:
        parts.append(
            "<verifier_feedback>\n"
            "This is a RETRY. Your prior draft was rejected by the Verifier. "
            "Address the specific claim(s) flagged below and do not re-emit "
            "the flagged text verbatim expecting a different verdict.\n"
            f"{verifier_feedback}\n"
            "</verifier_feedback>"
        )
    parts.append(_render_normalized_query(nq))
    parts.append(_render_chunks(chunks))
    parts.append(
        "Choose one of three decisions and submit it via the `submit_decision` "
        "tool: `answer`, `need_more_retrieval`, or `refuse`. You may first call "
        "`search_guidelines` or `get_full_section` if the current chunks are "
        "insufficient."
    )
    return "\n\n".join(parts)


# ---------------------------------------------------------------------------
# Response parsing helpers
# ---------------------------------------------------------------------------


def _extract_usage(response: Any) -> tuple[int, int, int]:
    """Pull (input, output, thinking) token counts from a Messages response.

    Supports both real SDK objects and dict-shaped fakes.
    """
    usage = getattr(response, "usage", None)
    if isinstance(usage, dict):
        return (
            int(usage.get("input_tokens", 0) or 0),
            int(usage.get("output_tokens", 0) or 0),
            int(
                usage.get("cache_creation_input_tokens", 0)
                or usage.get("thinking_tokens", 0)
                or 0
            ),
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


def _parse_filter_hints(raw: Any) -> RetrievalFilters:
    if raw is None:
        return RetrievalFilters()
    if not isinstance(raw, dict):
        return RetrievalFilters()
    # Drop keys the filter model doesn't know about; let Pydantic enforce
    # types on the rest. Unknown source types fall through validation.
    allowed = {
        "doc_ids",
        "source_types",
        "conditions",
        "min_year",
        "max_year",
        "section_types",
        "top_k",
    }
    clean = {k: v for k, v in raw.items() if k in allowed and v is not None}
    try:
        return RetrievalFilters(**clean)
    except ValidationError:
        return RetrievalFilters()


def _parse_submit_input(
    tool_input: dict[str, Any],
    streamed_text: str = "",
) -> DrafterResult | None:
    """Parse a `submit_decision` tool input into a DrafterResult.

    `streamed_text` is the accumulated text block the Drafter emitted
    BEFORE the tool call — used as `content` when the tool input
    doesn't include one (the new prompt contract). Legacy payloads
    that do include `content` inside the tool win, so rolling updates
    work either way.

    Returns None if the input is malformed — caller will refuse with
    CITATIONS_UNVERIFIABLE.
    """
    decision = tool_input.get("decision")
    if decision == "answer":
        answer_payload = tool_input.get("answer")
        if not isinstance(answer_payload, dict):
            return None
        # Prefer the explicit content field if the model still sends it
        # (older prompts / rollback safety). Fall back to the text block
        # the Drafter streamed before calling the tool.
        content = str(answer_payload.get("content") or streamed_text or "").strip()
        if not content:
            # No prose anywhere — can't verify a blank answer.
            return None
        try:
            claims = [Claim(**c) for c in answer_payload.get("claims", [])]
            citations = [Citation(**c) for c in answer_payload.get("citations", [])]
            answer = DraftAnswer(
                content=content,
                claims=claims,
                citations=citations,
            )
        except (ValidationError, TypeError):
            return None
        return DrafterAnswerDecision(answer=answer)

    if decision == "need_more_retrieval":
        filters = _parse_filter_hints(tool_input.get("filter_hints"))
        feedback = str(tool_input.get("feedback", "") or "")
        return DrafterNeedMoreRetrieval(filter_hints=filters, feedback=feedback)

    if decision == "refuse":
        reason_raw = tool_input.get("reason")
        if not isinstance(reason_raw, str) or reason_raw not in _DRAFTER_REFUSAL_REASONS:
            return None
        return DrafterRefuse(reason=RefusalReason(reason_raw))

    return None


# ---------------------------------------------------------------------------
# OpusDrafter
# ---------------------------------------------------------------------------


class OpusDrafter:
    """Drafter backed by Claude Opus 4.7 with adaptive thinking.

    Runs an Anthropic tool-use loop over up to `MAX_LOOP_ITERATIONS`
    iterations. Returns one of `DrafterAnswerDecision`,
    `DrafterNeedMoreRetrieval`, or `DrafterRefuse`.

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
        effort: str = DEFAULT_EFFORT,
    ) -> None:
        if anthropic_client is None and not api_key:
            raise ValueError(
                "OpusDrafter requires either an `anthropic_client` or an `api_key`."
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
        self.effort = effort
        self.last_usage: dict[str, Any] | None = None

    # ---------------------------------------------------------------- run

    async def run(
        self,
        state: QueryState,
        *,
        verifier_feedback: str | None = None,
    ) -> DrafterResult:
        nq = state.normalized_query
        if nq is None:
            # Should never happen — orchestrator guards this — but refuse
            # loudly rather than index into None.
            log.warning("drafter.missing_normalized_query", query_id=state.query_id)
            return DrafterRefuse(reason=RefusalReason.CITATIONS_UNVERIFIABLE)

        latest = state.latest_retrieval
        initial_chunks: list[Chunk] = list(latest.chunks) if latest is not None else []

        user_prompt = _build_initial_user_message(
            nq=nq,
            chunks=initial_chunks,
            verifier_feedback=verifier_feedback,
        )

        messages: list[dict[str, Any]] = [
            {"role": "user", "content": user_prompt},
        ]

        tools = _tool_specs()
        # Cache-shape: mark the system block for ephemeral caching. Tools
        # render in front of system in the Anthropic prefix, so a cache_control
        # on system covers tools + system together — ~10x cost reduction on
        # cache reads within the 5-minute TTL. Opus 4.7 cache minimum is 4096
        # tokens; our system + tools clear that threshold.
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
        # Opus 4.7: adaptive thinking only. `budget_tokens` / `enabled`
        # returns 400 on this model. `output_config.effort` tuning: xhigh
        # is safest/slowest, high is ~40-60% faster with a small quality
        # delta for structured tool-use loops.
        if self.thinking_budget > 0:
            kwargs_base["thinking"] = {"type": "adaptive"}
            kwargs_base["output_config"] = {"effort": self.effort}

        usage_totals = {"input_tokens": 0, "output_tokens": 0, "thinking_tokens": 0}
        started = time.perf_counter()
        decision: DrafterResult | None = None

        # Per-retriever state: each intra-drafter search increments the
        # attempt_num we hand to the Retriever but does NOT mutate
        # state.retrieval_attempts. See module docstring, point 1.
        base_attempt_num = (
            latest.attempt_num if latest is not None else 0
        )
        intra_retrieval_calls = 0

        iterations = 0
        while iterations < MAX_LOOP_ITERATIONS:
            iterations += 1

            # Heartbeat: Drafter turns can take 30-90s each under xhigh
            # effort. Emit a trace event before each LLM call so the UI
            # knows the phase is alive.
            state.append_trace(
                trace(
                    "drafter",
                    "thinking",
                    payload={"iteration": iterations},
                )
            )

            # Stream the response so text_delta events land as trace
            # events in real time. The new prompt contract asks the
            # Drafter to emit the full Bahasa answer as a text block
            # BEFORE calling submit_decision, which lets the SSE pump
            # forward each token to the UI as it's written — user sees
            # the answer composed live instead of waiting 60s blank.
            response, streamed_text = await self._stream_once(
                messages=list(messages),
                kwargs_base=kwargs_base,
                state=state,
                iteration=iterations,
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
                # Claude ended without submitting. See module docstring, point 2.
                log.warning(
                    "drafter.no_tool_call",
                    iteration=iterations,
                    stop_reason=stop_reason,
                    query_id=state.query_id,
                )
                decision = DrafterRefuse(reason=RefusalReason.CITATIONS_UNVERIFIABLE)
                break

            # Append the assistant turn verbatim so tool_use_id refs line up.
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

                if tool_name == "submit_decision":
                    parsed = _parse_submit_input(tool_input, streamed_text)
                    if parsed is None:
                        log.warning(
                            "drafter.submit_malformed",
                            iteration=iterations,
                            decision_raw=tool_input.get("decision"),
                            query_id=state.query_id,
                        )
                        decision = DrafterRefuse(
                            reason=RefusalReason.CITATIONS_UNVERIFIABLE
                        )
                    else:
                        decision = parsed
                    submitted = True
                    log.info(
                        "tool_dispatched",
                        tool="submit_decision",
                        iteration=iterations,
                        decision=tool_input.get("decision"),
                    )
                    break  # stop processing further blocks; loop exits

                # Helper tool dispatch.
                if tool_name == "search_guidelines":
                    intra_retrieval_calls += 1
                    result_payload = await self._dispatch_search(
                        nq=nq,
                        tool_input=tool_input,
                        attempt_num=base_attempt_num + intra_retrieval_calls,
                    )
                    state.append_trace(
                        trace(
                            "drafter",
                            "tool_search_guidelines",
                            payload={
                                "iteration": iterations,
                                "query": str(tool_input.get("query", ""))[:120],
                                "returned_chunks": len(
                                    result_payload.get("chunks", [])
                                ),
                            },
                        )
                    )
                    log.info(
                        "tool_dispatched",
                        tool="search_guidelines",
                        iteration=iterations,
                        intra_call=intra_retrieval_calls,
                        returned_chunks=len(result_payload.get("chunks", [])),
                    )
                elif tool_name == "get_full_section":
                    result_payload = self._dispatch_get_full_section(tool_input)
                    state.append_trace(
                        trace(
                            "drafter",
                            "tool_get_full_section",
                            payload={
                                "iteration": iterations,
                                "doc_id": str(tool_input.get("doc_id", ""))[:80],
                            },
                        )
                    )
                    log.info(
                        "tool_dispatched",
                        tool="get_full_section",
                        iteration=iterations,
                    )
                else:
                    log.warning(
                        "drafter.unknown_tool",
                        iteration=iterations,
                        tool=tool_name,
                    )
                    result_payload = {
                        "error": f"unknown tool: {tool_name!r}",
                    }

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
                # stop_reason was tool_use but no usable tool_use blocks
                # — treat as malformed.
                log.warning(
                    "drafter.empty_tool_use",
                    iteration=iterations,
                    query_id=state.query_id,
                )
                decision = DrafterRefuse(reason=RefusalReason.CITATIONS_UNVERIFIABLE)
                break

            messages.append({"role": "user", "content": tool_results})

        if decision is None:
            # Loop cap exceeded without submission.
            log.warning(
                "drafter.loop_cap_exceeded",
                iterations=iterations,
                query_id=state.query_id,
            )
            decision = DrafterRefuse(reason=RefusalReason.CITATIONS_UNVERIFIABLE)

        latency_ms = int((time.perf_counter() - started) * 1000)

        self.last_usage = {
            "input_tokens": usage_totals["input_tokens"],
            "output_tokens": usage_totals["output_tokens"],
            "thinking_tokens": usage_totals["thinking_tokens"],
            "model_id": self.model_id,
        }

        decision_name = getattr(decision, "decision", "unknown")
        log.info(
            "drafter.decided",
            decision=decision_name,
            iterations=iterations,
            intra_retrievals=intra_retrieval_calls,
            latency_ms=latency_ms,
            tokens_in=usage_totals["input_tokens"],
            tokens_out=usage_totals["output_tokens"],
            tokens_thinking=usage_totals["thinking_tokens"],
            query_id=state.query_id,
        )
        return decision

    # ----------------------------------------------------------- streaming

    async def _stream_once(
        self,
        *,
        messages: list[dict[str, Any]],
        kwargs_base: dict[str, Any],
        state: QueryState,
        iteration: int,
    ) -> tuple[Any, str]:
        """Single Anthropic messages.stream() turn.

        Side effect: emits a `drafter.text_delta` trace event for each
        text chunk as it streams, so the SSE pump forwards tokens to
        the UI in real time. Also emits a terminal `drafter.text_done`
        event with the full assembled text so UI layers that cache
        events can lock in the final content.

        Returns `(final_message, streamed_text)` — final_message has
        the same shape messages.create returns (usage, stop_reason,
        content blocks with tool inputs populated), so the existing
        tool-use dispatch loop downstream doesn't need any changes.
        """
        text_buffer: list[str] = []

        # Some fake-client paths in tests don't implement `.stream()`.
        # Fall back to `.create()` in that case so unit tests keep working.
        messages_api = self._client.messages
        stream_method = getattr(messages_api, "stream", None)
        if stream_method is None:
            response = messages_api.create(messages=messages, **kwargs_base)
            return response, ""

        # Anthropic's sync SDK would block the event loop end-to-end —
        # the SSE pump watching state.trace_events wouldn't get a chance
        # to forward deltas to the browser until the stream was done.
        # We push the whole sync stream onto a worker thread. The thread
        # still mutates state.trace_events directly (append is atomic
        # under the GIL) so the main loop's poller sees deltas land in
        # real time.
        def _run_stream() -> tuple[Any, str]:
            with stream_method(messages=messages, **kwargs_base) as stream:
                for event in stream:
                    etype = getattr(event, "type", None)
                    if etype != "content_block_delta":
                        continue
                    delta = getattr(event, "delta", None)
                    dtype = getattr(delta, "type", None)
                    if dtype == "text_delta":
                        chunk = getattr(delta, "text", "") or ""
                        if chunk:
                            text_buffer.append(chunk)
                            state.append_trace(
                                trace(
                                    "drafter",
                                    "text_delta",
                                    payload={
                                        "iteration": iteration,
                                        "text": chunk,
                                    },
                                )
                            )
                final_message = stream.get_final_message()
            return final_message, "".join(text_buffer).strip()

        final_message, streamed_text = await asyncio.to_thread(_run_stream)
        if streamed_text:
            state.append_trace(
                trace(
                    "drafter",
                    "text_done",
                    payload={
                        "iteration": iteration,
                        "chars": len(streamed_text),
                    },
                )
            )
        return final_message, streamed_text

    # ----------------------------------------------------------- dispatchers

    async def _dispatch_search(
        self,
        *,
        nq: NormalizedQuery,
        tool_input: dict[str, Any],
        attempt_num: int,
    ) -> dict[str, Any]:
        """Run a narrower retrieval inside the drafter's tool-use loop.

        We build a `NormalizedQuery` with the Claude-supplied `query` string
        substituted into `structured_query`; all other fields are inherited
        from the original query so downstream filters still make sense.
        """
        query_text = str(tool_input.get("query") or nq.structured_query)
        filters = _parse_filter_hints(tool_input.get("filters"))

        sub_query = NormalizedQuery(
            structured_query=query_text,
            condition_tags=list(nq.condition_tags),
            intent=nq.intent,
            patient_context=nq.patient_context,
            keywords_id=list(nq.keywords_id),
            keywords_en=list(nq.keywords_en),
            red_flags=list(nq.red_flags),
        )
        attempt = await self.retriever.search(
            sub_query, filters, attempt_num=attempt_num
        )
        return {
            "chunks": [
                {
                    "key": f"{c.doc_id}:p{c.page}:{c.section_slug}",
                    "doc_id": c.doc_id,
                    "page": c.page,
                    "section_slug": c.section_slug,
                    "section_path": c.section_path,
                    "text": c.text,
                    "year": c.year,
                    "source_type": c.source_type,
                    "score": c.score,
                }
                for c in attempt.chunks
            ],
        }

    def _dispatch_get_full_section(
        self, tool_input: dict[str, Any]
    ) -> dict[str, Any]:
        """Delegate to `retriever.get_full_section` if present.

        `LocalRetriever` exposes this method; the test `FakeRetriever` does
        not. Return an error structure rather than raising so Claude can
        continue the loop.
        """
        fn = getattr(self.retriever, "get_full_section", None)
        if not callable(fn):
            return {
                "error": (
                    "get_full_section is not available on this retriever. "
                    "Proceed with the chunks already in context."
                ),
            }
        try:
            result = fn(
                str(tool_input.get("doc_id", "")),
                str(tool_input.get("section_path", "")),
            )
        except Exception as exc:
            # Surface the failure to Claude rather than crashing the loop —
            # helper tools are best-effort.
            return {"error": f"get_full_section failed: {exc}"}
        if isinstance(result, dict):
            return result
        return {"section_text": str(result)}


__all__ = ["DrafterPromptError", "OpusDrafter"]
