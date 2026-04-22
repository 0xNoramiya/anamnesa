"""BudgetTracker unit tests."""

from __future__ import annotations

import pytest

from core.budget import BudgetExceededError, BudgetLimits, BudgetTracker
from core.refusals import RefusalReason


def _fake_clock(ticks: list[float]) -> callable:
    """Return a monotonic() replacement that yields from `ticks` in order."""
    it = iter(ticks)

    def _clock() -> float:
        return next(it)

    return _clock


def test_retrieval_budget_tripped_on_4th_attempt() -> None:
    b = BudgetTracker(BudgetLimits(max_retrieval_attempts=3))
    b.charge_retrieval()
    b.charge_retrieval()
    b.charge_retrieval()
    with pytest.raises(BudgetExceededError) as exc:
        b.charge_retrieval()
    assert exc.value.reason is RefusalReason.RETRIEVAL_BUDGET_EXHAUSTED


def test_drafter_budget_tripped_on_4th_call() -> None:
    b = BudgetTracker(BudgetLimits(max_drafter_calls=3))
    for _ in range(3):
        b.charge_drafter()
    with pytest.raises(BudgetExceededError) as exc:
        b.charge_drafter()
    assert exc.value.reason is RefusalReason.DRAFTER_BUDGET_EXHAUSTED


def test_verifier_budget_tripped_on_3rd_call() -> None:
    b = BudgetTracker(BudgetLimits(max_verifier_calls=2))
    b.charge_verifier()
    b.charge_verifier()
    with pytest.raises(BudgetExceededError) as exc:
        b.charge_verifier()
    assert exc.value.reason is RefusalReason.VERIFIER_BUDGET_EXHAUSTED


def test_token_budget_tripped_when_total_exceeds_limit() -> None:
    b = BudgetTracker(BudgetLimits(max_total_tokens=100))
    b.charge_tokens(60)
    with pytest.raises(BudgetExceededError) as exc:
        b.charge_tokens(50)
    assert exc.value.reason is RefusalReason.TOKEN_BUDGET_EXHAUSTED


def test_wall_clock_exceeded_trips_on_next_charge() -> None:
    # 0.0 = construction, 0.1 = first check (ok), 31.0 = second check (over 30s).
    clock = _fake_clock([0.0, 0.1, 31.0])
    b = BudgetTracker(BudgetLimits(max_wall_clock_seconds=30.0), monotonic=clock)
    b.charge_retrieval()
    with pytest.raises(BudgetExceededError) as exc:
        b.charge_retrieval()
    assert exc.value.reason is RefusalReason.WALL_CLOCK_EXHAUSTED


def test_healthy_budget_does_not_raise() -> None:
    b = BudgetTracker(BudgetLimits())
    b.charge_retrieval()
    b.charge_drafter()
    b.charge_verifier()
    b.charge_tokens(1_000)
    # No exception is the assertion.
