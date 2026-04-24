"""Control loop for the Anamnesa agentic retrieval system.

Implements the loop specified in CLAUDE.md > "Control loop". Agents are
injected as Protocol instances so tests can swap in deterministic fakes.

Design rules (must not drift):
  - Fields accumulate in `QueryState`; nothing is overwritten.
  - Refusal is a first-class terminal state — never swallow silently.
  - Agent exceptions propagate; the orchestrator does not downgrade
    `RuntimeError` to a refusal.
  - BudgetExceededError is the ONE exception class the orchestrator
    converts to a refusal (because it represents an intentional
    guard-rail stop).
"""

from __future__ import annotations

import time

import structlog

from agents.base import (
    Drafter,
    Normalizer,
    NormalizerRefusal,
    Retriever,
    Verifier,
)
from core.budget import BudgetExceededError, BudgetLimits, BudgetTracker
from core.cache import AnswerCache, cache_key
from core.refusals import RefusalReason, message_for
from core.state import (
    Citation,
    CurrencyFlag,
    DraftAnswer,
    DrafterAnswerDecision,
    DrafterNeedMoreRetrieval,
    DrafterRefuse,
    FinalResponse,
    QueryState,
    RetrievalFilters,
    RetrievalHint,
    VerificationResult,
)
from core.trace import trace

log = structlog.get_logger("anamnesa.orchestrator")


class Orchestrator:
    """Drives a single query through the agent loop."""

    def __init__(
        self,
        *,
        normalizer: Normalizer,
        retriever: Retriever,
        drafter: Drafter,
        verifier: Verifier,
        limits: BudgetLimits | None = None,
        cache: AnswerCache | None = None,
    ) -> None:
        self.normalizer = normalizer
        self.retriever = retriever
        self.drafter = drafter
        self.verifier = verifier
        self.limits = limits or BudgetLimits()
        self.cache = cache

    async def run(
        self,
        user_query: str,
        *,
        state: QueryState | None = None,
        prior_turn: dict[str, str] | None = None,
    ) -> QueryState:
        """Drive a single query through the agent loop.

        `state` may be pre-constructed by a caller that needs a live handle
        to the state (e.g. the SSE server watching `state.trace_events`
        for stream events). If omitted, a fresh state is built here.

        `prior_turn` (keys: "query", "answer") enables multi-turn chat —
        the Normalizer sees the last Q/A and can condense a terse
        follow-up like "dan kalau anak?" into a standalone query.
        """
        if state is None:
            state = QueryState(original_query=user_query)
        budget = BudgetTracker(self.limits)
        started = time.monotonic()

        state.append_trace(
            trace(
                "orchestrator",
                "query_started",
                payload={
                    "query_id": state.query_id,
                    "has_prior_turn": prior_turn is not None,
                },
            )
        )

        try:
            # Fast path: answer cache runs BEFORE normalize so a hit skips all
            # LLM calls including Haiku. Multi-turn queries skip the cache —
            # a follow-up like "dan kalau anak?" resolves against prior context.
            if prior_turn is None and self._try_serve_from_cache(state, started):
                return state

            await self._normalize(state, prior_turn=prior_turn)
            if state.refusal_reason is not None:
                return self._finalize_refusal(state, budget, started)

            await self._retrieval_draft_verify_loop(state, budget)
            if state.refusal_reason is not None:
                return self._finalize_refusal(state, budget, started)

            return self._finalize_success(state, budget, started)

        except BudgetExceededError as exc:
            state.refusal_reason = exc.reason
            state.append_trace(
                trace(
                    "orchestrator",
                    "budget_exceeded",
                    payload={"reason": exc.reason.value, "detail": exc.detail},
                )
            )
            return self._finalize_refusal(state, budget, started)

    async def _normalize(
        self,
        state: QueryState,
        *,
        prior_turn: dict[str, str] | None = None,
    ) -> None:
        t0 = time.monotonic()
        result = await self.normalizer.run(state, prior_turn=prior_turn)
        latency_ms = int((time.monotonic() - t0) * 1000)
        self._charge_agent_usage(state, "normalizer", self.normalizer)

        if isinstance(result, NormalizerRefusal):
            state.refusal_reason = result.reason
            state.append_trace(
                trace(
                    "normalizer",
                    "refused",
                    payload={"reason": result.reason.value},
                    latency_ms=latency_ms,
                )
            )
            return

        state.normalized_query = result
        state.append_trace(
            trace(
                "normalizer",
                "normalized",
                payload={
                    "intent": result.intent,
                    "condition_tags": result.condition_tags,
                    "patient_context": result.patient_context,
                },
                latency_ms=latency_ms,
            )
        )

    async def _retrieval_draft_verify_loop(
        self, state: QueryState, budget: BudgetTracker
    ) -> None:
        """Retrieval + draft + verification loop.

        Branches:
          - Drafter says `need_more_retrieval` → charge another retrieval
            + drafter call, loop.
          - Drafter says `refuse` → set refusal, stop.
          - Drafter produces answer → verify. If unsupported, loop back
            with Verifier feedback for ONE retry only.
        """
        assert state.normalized_query is not None

        verifier_retries_left = 1
        verifier_feedback: str | None = None
        next_filters = RetrievalFilters()

        while True:
            budget.charge_retrieval()
            attempt_num = budget.retrieval_attempts
            attempt = await self.retriever.search(
                state.normalized_query, next_filters, attempt_num=attempt_num
            )
            state.append_retrieval(attempt)
            # Top-5 chunk previews surface on SSE ~5s in so the UI has something
            # concrete before the Drafter + Verifier (120-180s) finishes.
            chunk_previews = []
            for chunk in attempt.chunks[:5]:
                text = " ".join(chunk.text.split())
                if len(text) > 220:
                    text = text[:219] + "…"
                chunk_previews.append(
                    {
                        "doc_id": chunk.doc_id,
                        "page": chunk.page,
                        "section_slug": chunk.section_slug,
                        "year": chunk.year,
                        "source_type": chunk.source_type,
                        "score": round(chunk.score, 3),
                        "excerpt": text,
                    }
                )
            per_doc: dict[str, int] = {}
            for chunk in attempt.chunks:
                per_doc[chunk.doc_id] = per_doc.get(chunk.doc_id, 0) + 1
            doc_summary = [
                {"doc_id": d, "hits": n}
                for d, n in sorted(per_doc.items(), key=lambda kv: -kv[1])[:6]
            ]
            state.append_trace(
                trace(
                    "retriever",
                    "searched",
                    payload={
                        "attempt": attempt_num,
                        "chunks": len(attempt.chunks),
                        "filters": next_filters.model_dump(exclude_none=True),
                        "previews": chunk_previews,
                        "docs": doc_summary,
                    },
                    latency_ms=attempt.latency_ms,
                )
            )

            budget.charge_drafter()
            t0 = time.monotonic()
            draft_result = await self.drafter.run(state, verifier_feedback=verifier_feedback)
            drafter_latency = int((time.monotonic() - t0) * 1000)
            self._charge_agent_usage(state, "drafter", self.drafter)
            verifier_feedback = None

            if isinstance(draft_result, DrafterNeedMoreRetrieval):
                next_filters = draft_result.filter_hints
                state.append_trace(
                    trace(
                        "drafter",
                        "need_more_retrieval",
                        payload={"feedback": draft_result.feedback},
                        latency_ms=drafter_latency,
                    )
                )
                continue

            if isinstance(draft_result, DrafterRefuse):
                state.refusal_reason = draft_result.reason
                state.append_trace(
                    trace(
                        "drafter",
                        "refused",
                        payload={"reason": draft_result.reason.value},
                        latency_ms=drafter_latency,
                    )
                )
                return

            assert isinstance(draft_result, DrafterAnswerDecision)
            state.draft_answer = draft_result.answer
            state.append_trace(
                trace(
                    "drafter",
                    "drafted",
                    payload={
                        "citations": len(draft_result.answer.citations),
                        "claims": len(draft_result.answer.claims),
                    },
                    latency_ms=drafter_latency,
                )
            )

            budget.charge_verifier()
            t0 = time.monotonic()
            verification: VerificationResult = await self.verifier.run(state)
            verifier_latency = int((time.monotonic() - t0) * 1000)
            self._charge_agent_usage(state, "verifier", self.verifier)
            state.verification = verification
            state.currency_flags = list(verification.currency_flags)
            state.append_trace(
                trace(
                    "verifier",
                    "verified",
                    payload={
                        "has_unsupported": verification.has_unsupported,
                        "supported": sum(
                            1 for v in verification.verifications if v.status == "supported"
                        ),
                        "unsupported": sum(
                            1 for v in verification.verifications if v.status == "unsupported"
                        ),
                    },
                    latency_ms=verifier_latency,
                )
            )

            if not verification.has_unsupported:
                return

            if verifier_retries_left <= 0:
                state.refusal_reason = RefusalReason.CITATIONS_UNVERIFIABLE
                state.append_trace(
                    trace(
                        "orchestrator",
                        "verifier_exhausted",
                        payload={"reason": RefusalReason.CITATIONS_UNVERIFIABLE.value},
                    )
                )
                return

            verifier_retries_left -= 1
            verifier_feedback = verification.feedback_for_drafter or ""
            state.append_trace(
                trace(
                    "orchestrator",
                    "drafter_retry_requested",
                    payload={"retries_left": verifier_retries_left},
                )
            )

    @staticmethod
    def _charge_agent_usage(state: QueryState, agent_name: str, agent: object) -> None:
        """Fold the agent's `last_usage` into `state.cost`. Tolerant of agents
        without the attribute or with it unset (test fakes, early returns)."""
        usage = getattr(agent, "last_usage", None)
        if not usage:
            return
        state.cost.add(
            agent_name,
            input_tokens=int(usage.get("input_tokens", 0) or 0),
            output_tokens=int(usage.get("output_tokens", 0) or 0),
            thinking_tokens=int(usage.get("thinking_tokens", 0) or 0),
        )

    def _try_serve_from_cache(self, state: QueryState, started: float) -> bool:
        """Look up the raw user query in the answer cache.

        Returns True iff a hit was replayed into `state` (caller should return).
        Replay semantics: emit `cache_hit`, replay the cached trace events
        verbatim so SSE looks identical to a live run, then rebind `query_id`
        / `from_cache` on the FinalResponse.
        """
        if self.cache is None:
            return False
        key = cache_key(state.original_query)
        hit = self.cache.get(key)
        if hit is None:
            return False

        state.append_trace(
            trace(
                "orchestrator",
                "cache_hit",
                payload={
                    "key": key,
                    "age_s": round(hit.age_seconds, 1),
                    "cached_refusal": (
                        hit.final_response.refusal_reason.value
                        if hit.final_response.refusal_reason
                        else None
                    ),
                },
            )
        )
        for ev in hit.trace_events:
            state.append_trace(ev)

        state.final_response = hit.final_response.model_copy(
            update={
                "query_id": state.query_id,
                "from_cache": True,
                "cached_age_s": round(hit.age_seconds, 1),
            }
        )
        if hit.final_response.refusal_reason is not None:
            state.refusal_reason = hit.final_response.refusal_reason

        state.cost.wall_clock_ms = int((time.monotonic() - started) * 1000)
        state.append_trace(
            trace(
                "orchestrator",
                "query_completed",
                payload={
                    "citations": len(state.final_response.citations),
                    "currency_flags": len(state.final_response.currency_flags),
                    "wall_clock_ms": state.cost.wall_clock_ms,
                    "from_cache": True,
                },
            )
        )
        return True

    def _store_in_cache(self, state: QueryState) -> None:
        """Persist a freshly-computed FinalResponse.

        Must be called AFTER `final_response` is populated but BEFORE any
        cache_hit trace is replayed — only live-run events belong in storage.
        """
        if self.cache is None:
            return
        if state.final_response is None:
            return
        # `query_completed` is regenerated on replay with fresh timing.
        replayable = [
            e
            for e in state.trace_events
            if not (e.agent == "orchestrator" and e.event_type == "query_completed")
        ]
        try:
            self.cache.put(cache_key(state.original_query), state.final_response, replayable)
        except Exception as exc:
            # Cache is best-effort — a persistence failure must not fail the query.
            log.warning("cache.put_failed", error=str(exc), query_id=state.query_id)

    def _finalize_success(
        self, state: QueryState, budget: BudgetTracker, started: float
    ) -> QueryState:
        assert state.draft_answer is not None
        state.cost.wall_clock_ms = int((time.monotonic() - started) * 1000)
        state.final_response = _assemble_success(state)
        self._store_in_cache(state)
        state.append_trace(
            trace(
                "orchestrator",
                "query_completed",
                payload={
                    "citations": len(state.final_response.citations),
                    "currency_flags": len(state.final_response.currency_flags),
                    "wall_clock_ms": state.cost.wall_clock_ms,
                    "total_tokens": budget.total_tokens,
                },
            )
        )
        return state

    def _finalize_refusal(
        self, state: QueryState, budget: BudgetTracker, started: float
    ) -> QueryState:
        reason = state.refusal_reason
        assert reason is not None, "finalize_refusal called with no refusal_reason"
        state.cost.wall_clock_ms = int((time.monotonic() - started) * 1000)
        state.final_response = FinalResponse(
            query_id=state.query_id,
            answer_markdown=message_for(reason),
            citations=[],
            currency_flags=[],
            refusal_reason=reason,
            retrieval_preview=_build_retrieval_preview(state, reason),
        )
        self._store_in_cache(state)
        state.append_trace(
            trace(
                "orchestrator",
                "query_completed",
                payload={
                    "refusal_reason": reason.value,
                    "wall_clock_ms": state.cost.wall_clock_ms,
                    "total_tokens": budget.total_tokens,
                },
            )
        )
        return state


def _assemble_success(state: QueryState) -> FinalResponse:
    answer: DraftAnswer = state.draft_answer  # type: ignore[assignment]
    citations: list[Citation] = list(answer.citations)
    flags: list[CurrencyFlag] = list(state.currency_flags)
    return FinalResponse(
        query_id=state.query_id,
        answer_markdown=answer.content,
        citations=citations,
        currency_flags=flags,
    )


# Refusals where the near-miss chunks are useful to show the user.
# Out-of-scope / patient-specific refusals skip retrieval entirely; budget /
# verifier exhaustion can have chunks but they're noisy.
_PREVIEW_REFUSAL_REASONS = frozenset(
    {
        RefusalReason.CORPUS_SILENT,
        RefusalReason.ALL_SUPERSEDED_NO_CURRENT,
        RefusalReason.CITATIONS_UNVERIFIABLE,
    }
)
_RETRIEVAL_PREVIEW_MAX = 3
_RETRIEVAL_PREVIEW_CHARS = 220


def _build_retrieval_preview(
    state: QueryState, reason: RefusalReason
) -> list[RetrievalHint]:
    if reason not in _PREVIEW_REFUSAL_REASONS:
        return []
    latest = state.latest_retrieval
    if latest is None or not latest.chunks:
        return []
    preview: list[RetrievalHint] = []
    for chunk in latest.chunks[:_RETRIEVAL_PREVIEW_MAX]:
        text = " ".join(chunk.text.split())
        if len(text) > _RETRIEVAL_PREVIEW_CHARS:
            text = text[: _RETRIEVAL_PREVIEW_CHARS - 1] + "…"
        preview.append(
            RetrievalHint(
                doc_id=chunk.doc_id,
                page=chunk.page,
                section_slug=chunk.section_slug,
                section_path=chunk.section_path,
                text_preview=text,
                year=chunk.year,
                source_type=chunk.source_type,
                score=chunk.score,
            )
        )
    return preview
