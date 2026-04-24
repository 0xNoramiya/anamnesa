"""Drafter agent — Opus 4.7 with adaptive thinking.

Runs an Anthropic tool-use loop that terminates with one of three decisions
via the `submit_decision` tool:
  - `answer` — cited Bahasa draft, one citation per claim
  - `need_more_retrieval` — ask the orchestrator to search again
  - `refuse` — corpus silent / out of scope / patient-specific

Invariants:
- Intra-loop `search_guidelines` calls do NOT mutate `state.retrieval_attempts`
  — that budget belongs to the orchestrator. Re-retrieval requests surface as
  the `need_more_retrieval` decision instead.
- Malformed output (no `submit_decision`, loop cap exceeded, unparseable tool
  input) maps to `CITATIONS_UNVERIFIABLE`. There is no dedicated "drafter
  malformed" refusal enum.
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
MAX_OUTPUT_TOKENS = 16_000
# thinking_budget=0: adaptive thinking batches all output through the tool
# call and disables text streaming, which defeats the live-answer UX.
DEFAULT_THINKING_BUDGET = 0
DEFAULT_EFFORT = "xhigh"
MAX_LOOP_ITERATIONS = 8
PROMPT_PATH = Path(__file__).parent / "prompts" / "drafter.md"

# Refusal reasons the Drafter is allowed to emit. Anything else in the `refuse`
# branch is treated as malformed and collapsed to CITATIONS_UNVERIFIABLE.
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
    """Minimal shape of the Anthropic SDK client used by this agent."""

    messages: Any


def _build_client(api_key: str) -> _AnthropicLike:
    from anthropic import Anthropic

    return Anthropic(api_key=api_key)


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
        # `content`, if provided, wins over the streamed text block.
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


def _render_chunk(chunk: Chunk) -> str:
    key = f"{chunk.doc_id}:p{chunk.page}:{chunk.section_slug}"
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


def _extract_usage(response: Any) -> tuple[int, int, int]:
    """Pull (input, output, thinking) token counts from a Messages response."""
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

    `streamed_text` is the text block emitted before the tool call; used as
    `content` when the payload omits it. Explicit `content` wins.

    Returns None on malformed input — caller refuses with CITATIONS_UNVERIFIABLE.
    """
    decision = tool_input.get("decision")
    if decision == "answer":
        answer_payload = tool_input.get("answer")
        if not isinstance(answer_payload, dict):
            return None
        content = str(answer_payload.get("content") or streamed_text or "").strip()
        if not content:
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


class OpusDrafter:
    """Drafter backed by Claude Opus 4.7 with adaptive thinking.

    Runs an Anthropic tool-use loop up to `MAX_LOOP_ITERATIONS` iterations and
    returns a `DrafterAnswerDecision`, `DrafterNeedMoreRetrieval`, or
    `DrafterRefuse`.
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

    async def run(
        self,
        state: QueryState,
        *,
        verifier_feedback: str | None = None,
    ) -> DrafterResult:
        nq = state.normalized_query
        if nq is None:
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
        # `cache_control` on the system block covers tools+system together
        # (tools render in front of system in the prefix) — ~10x cost cut on
        # cache hits within the 5min TTL. System+tools clear the 4096-token
        # Opus 4.7 cache minimum.
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
        # Opus 4.7 supports only adaptive thinking; `budget_tokens` / `enabled`
        # returns HTTP 400.
        if self.thinking_budget > 0:
            kwargs_base["thinking"] = {"type": "adaptive"}
            kwargs_base["output_config"] = {"effort": self.effort}

        usage_totals = {"input_tokens": 0, "output_tokens": 0, "thinking_tokens": 0}
        started = time.perf_counter()
        decision: DrafterResult | None = None

        # Intra-drafter searches increment attempt_num but do NOT mutate
        # state.retrieval_attempts — the orchestrator owns that budget.
        base_attempt_num = (
            latest.attempt_num if latest is not None else 0
        )
        intra_retrieval_calls = 0

        iterations = 0
        while iterations < MAX_LOOP_ITERATIONS:
            iterations += 1

            # Heartbeat: xhigh turns run 30-90s each; emit a trace so the UI
            # knows the phase is alive.
            state.append_trace(
                trace(
                    "drafter",
                    "thinking",
                    payload={"iteration": iterations},
                )
            )

            # Prompt contract: Drafter emits the full Bahasa answer as a text
            # block BEFORE submit_decision, enabling live composition in UI.
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
                log.warning(
                    "drafter.no_tool_call",
                    iteration=iterations,
                    stop_reason=stop_reason,
                    query_id=state.query_id,
                )
                decision = DrafterRefuse(reason=RefusalReason.CITATIONS_UNVERIFIABLE)
                break

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
                    break

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
                log.warning(
                    "drafter.empty_tool_use",
                    iteration=iterations,
                    query_id=state.query_id,
                )
                decision = DrafterRefuse(reason=RefusalReason.CITATIONS_UNVERIFIABLE)
                break

            messages.append({"role": "user", "content": tool_results})

        if decision is None:
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

    async def _stream_once(
        self,
        *,
        messages: list[dict[str, Any]],
        kwargs_base: dict[str, Any],
        state: QueryState,
        iteration: int,
    ) -> tuple[Any, str]:
        """Single Anthropic messages.stream() turn.

        Emits `drafter.text_delta` traces per streamed chunk and a terminal
        `drafter.text_done` so the SSE pump forwards tokens live. Returns
        `(final_message, streamed_text)` — `final_message` has the same shape
        as `messages.create` returns.
        """
        text_buffer: list[str] = []

        # Fallback to `.create()` for test fakes that don't implement `.stream()`.
        messages_api = self._client.messages
        stream_method = getattr(messages_api, "stream", None)
        if stream_method is None:
            response = messages_api.create(messages=messages, **kwargs_base)
            return response, ""

        # Push the sync SDK stream onto a worker thread so it doesn't block the
        # event loop end-to-end. Appends to state.trace_events from the thread
        # are safe (atomic under GIL); the main-loop poller sees deltas live.
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

    async def _dispatch_search(
        self,
        *,
        nq: NormalizedQuery,
        tool_input: dict[str, Any],
        attempt_num: int,
    ) -> dict[str, Any]:
        """Run a narrower retrieval inside the drafter's tool-use loop.

        Builds a `NormalizedQuery` with Claude's `query` string in
        `structured_query`; other fields inherit from the original query so
        downstream filters still make sense.
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

        Returns an error struct (not an exception) so Claude can continue the
        loop.
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
            return {"error": f"get_full_section failed: {exc}"}
        if isinstance(result, dict):
            return result
        return {"section_text": str(result)}


__all__ = ["DrafterPromptError", "OpusDrafter"]
