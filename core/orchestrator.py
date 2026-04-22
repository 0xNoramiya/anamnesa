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
    ) -> None:
        self.normalizer = normalizer
        self.retriever = retriever
        self.drafter = drafter
        self.verifier = verifier
        self.limits = limits or BudgetLimits()

    async def run(self, user_query: str) -> QueryState:
        state = QueryState(original_query=user_query)
        budget = BudgetTracker(self.limits)
        started = time.monotonic()

        state.append_trace(
            trace("orchestrator", "query_started", payload={"query_id": state.query_id})
        )

        try:
            await self._normalize(state)
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

    # ------------------------------------------------------------------ stages

    async def _normalize(self, state: QueryState) -> None:
        t0 = time.monotonic()
        result = await self.normalizer.run(state)
        latency_ms = int((time.monotonic() - t0) * 1000)

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
            # --- retrieval ---
            budget.charge_retrieval()
            attempt_num = budget.retrieval_attempts
            attempt = await self.retriever.search(
                state.normalized_query, next_filters, attempt_num=attempt_num
            )
            state.append_retrieval(attempt)
            state.append_trace(
                trace(
                    "retriever",
                    "searched",
                    payload={
                        "attempt": attempt_num,
                        "chunks": len(attempt.chunks),
                        "filters": next_filters.model_dump(exclude_none=True),
                    },
                    latency_ms=attempt.latency_ms,
                )
            )

            # --- drafter ---
            budget.charge_drafter()
            t0 = time.monotonic()
            draft_result = await self.drafter.run(state, verifier_feedback=verifier_feedback)
            drafter_latency = int((time.monotonic() - t0) * 1000)
            verifier_feedback = None  # consumed

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
                continue  # loop; budget.charge_retrieval may now refuse.

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

            # DrafterAnswerDecision
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

            # --- verifier ---
            budget.charge_verifier()
            t0 = time.monotonic()
            verification: VerificationResult = await self.verifier.run(state)
            verifier_latency = int((time.monotonic() - t0) * 1000)
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
                return  # success; outer method will finalize.

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
            # Loop back: no new retrieval necessary unless Drafter then asks
            # for it. Reuse the last filters so retrieval is cheap.
            # Intentionally continue to the top: the next iteration will
            # consume another retrieval slot. This is a deliberate choice —
            # re-running retrieval with identical filters is cheap relative
            # to the LLM calls and keeps the loop structurally simple.

    # ------------------------------------------------------------------ finalize

    def _finalize_success(
        self, state: QueryState, budget: BudgetTracker, started: float
    ) -> QueryState:
        assert state.draft_answer is not None
        state.cost.wall_clock_ms = int((time.monotonic() - started) * 1000)
        state.final_response = _assemble_success(state)
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
        )
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


# ---------------------------------------------------------------------------
# Assembly helpers
# ---------------------------------------------------------------------------


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
