"""Per-query budget guardrails — hard stops, non-negotiable.

Per CLAUDE.md these exist so one bad query cannot eat 10% of the hackathon
credit budget. Exceeding any limit aborts cleanly with a refusal.
"""

from __future__ import annotations

import os
import time
from collections.abc import Callable
from dataclasses import dataclass

from core.refusals import RefusalReason


@dataclass(frozen=True)
class BudgetLimits:
    """Hard-stop limits for a single query, tunable via env."""

    max_retrieval_attempts: int = 3
    max_drafter_calls: int = 3
    max_verifier_calls: int = 2
    max_total_tokens: int = 150_000
    max_wall_clock_seconds: float = 30.0

    @classmethod
    def from_env(cls) -> BudgetLimits:
        return cls(
            max_retrieval_attempts=int(
                os.getenv("ANAMNESA_MAX_RETRIEVAL_ATTEMPTS", 3)
            ),
            max_drafter_calls=int(os.getenv("ANAMNESA_MAX_DRAFTER_CALLS", 3)),
            max_verifier_calls=int(os.getenv("ANAMNESA_MAX_VERIFIER_CALLS", 2)),
            max_total_tokens=int(
                os.getenv("ANAMNESA_MAX_TOTAL_TOKENS_PER_QUERY", 150_000)
            ),
            max_wall_clock_seconds=float(
                os.getenv("ANAMNESA_MAX_WALL_CLOCK_SECONDS", 30)
            ),
        )


class BudgetExceededError(Exception):
    """Raised when a budget limit trips. `reason` is the refusal to surface."""

    def __init__(self, reason: RefusalReason, detail: str = "") -> None:
        super().__init__(f"{reason.value}: {detail}" if detail else reason.value)
        self.reason = reason
        self.detail = detail


class BudgetTracker:
    """Tracks per-query resource usage and raises on overrun.

    Counters are incremented explicitly by the orchestrator *before* making
    the corresponding call so we never leak a call past the limit.
    """

    def __init__(
        self,
        limits: BudgetLimits,
        monotonic: Callable[[], float] = time.monotonic,
    ) -> None:
        self.limits = limits
        self._monotonic = monotonic
        self._start = monotonic()
        self.retrieval_attempts = 0
        self.drafter_calls = 0
        self.verifier_calls = 0
        self.total_tokens = 0

    def elapsed_seconds(self) -> float:
        return self._monotonic() - self._start

    def check_wall_clock(self) -> None:
        elapsed = self.elapsed_seconds()
        if elapsed > self.limits.max_wall_clock_seconds:
            raise BudgetExceededError(
                RefusalReason.WALL_CLOCK_EXHAUSTED,
                f"{elapsed:.1f}s > {self.limits.max_wall_clock_seconds}s",
            )

    def charge_retrieval(self) -> None:
        """Call before starting a retrieval attempt."""
        self.check_wall_clock()
        if self.retrieval_attempts >= self.limits.max_retrieval_attempts:
            raise BudgetExceededError(RefusalReason.RETRIEVAL_BUDGET_EXHAUSTED)
        self.retrieval_attempts += 1

    def charge_drafter(self) -> None:
        """Call before invoking the drafter."""
        self.check_wall_clock()
        if self.drafter_calls >= self.limits.max_drafter_calls:
            raise BudgetExceededError(RefusalReason.DRAFTER_BUDGET_EXHAUSTED)
        self.drafter_calls += 1

    def charge_verifier(self) -> None:
        """Call before invoking the verifier."""
        self.check_wall_clock()
        if self.verifier_calls >= self.limits.max_verifier_calls:
            raise BudgetExceededError(RefusalReason.VERIFIER_BUDGET_EXHAUSTED)
        self.verifier_calls += 1

    def charge_tokens(self, tokens: int) -> None:
        """Call after an LLM response arrives."""
        self.total_tokens += tokens
        if self.total_tokens > self.limits.max_total_tokens:
            raise BudgetExceededError(
                RefusalReason.TOKEN_BUDGET_EXHAUSTED,
                f"{self.total_tokens} > {self.limits.max_total_tokens}",
            )
