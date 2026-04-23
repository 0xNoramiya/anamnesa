"""Tests for `core.cache` — canonical key, TTL, replay semantics, and
the orchestrator cache-hit short-circuit path."""

from __future__ import annotations

import time
from pathlib import Path

import pytest

from core.budget import BudgetLimits
from core.cache import AnswerCache, cache_key, cache_key_from_normalized
from core.orchestrator import Orchestrator
from core.refusals import RefusalReason
from core.state import FinalResponse, NormalizedQuery
from core.trace import trace
from tests.fakes import (
    FakeDrafter,
    FakeNormalizer,
    FakeRetriever,
    FakeVerifier,
    drafter_answer,
    make_chunk,
    make_normalized,
    verification_all_supported,
)


# ---------------------------------------------------------------------------
# cache_key canonicalization — raw user query
# ---------------------------------------------------------------------------


def test_cache_key_is_deterministic() -> None:
    q = "DBD anak derajat 2 tata laksana cairan awal"
    assert cache_key(q) == cache_key(q)
    assert len(cache_key(q)) == 16


def test_cache_key_normalizes_whitespace_and_case() -> None:
    a = "DBD   anak\nDerajat 2   tata laksana"
    b = "dbd anak derajat 2 tata laksana"
    assert cache_key(a) == cache_key(b)


def test_cache_key_diverges_on_content() -> None:
    assert cache_key("DBD anak") != cache_key("DBD dewasa")
    assert cache_key("TB paru") != cache_key("TB paru anak")


# ---------------------------------------------------------------------------
# cache_key_from_normalized — legacy helper still works
# ---------------------------------------------------------------------------


def test_cache_key_from_normalized_is_stable() -> None:
    nq = NormalizedQuery(
        structured_query="DBD derajat 2",
        intent="tatalaksana",
        patient_context="pediatric",
        condition_tags=["dbd"],
    )
    assert cache_key_from_normalized(nq) == cache_key_from_normalized(nq)


# ---------------------------------------------------------------------------
# AnswerCache — put/get/TTL
# ---------------------------------------------------------------------------


def _final(reason: RefusalReason | None = None) -> FinalResponse:
    return FinalResponse(
        query_id="Q1",
        answer_markdown="jawaban [[doc:p1:slug]]",
        citations=[],
        currency_flags=[],
        refusal_reason=reason,
    )


def test_put_and_get_roundtrip(tmp_path: Path) -> None:
    cache = AnswerCache(tmp_path / "cache.db")
    events = [trace("orchestrator", "query_started", payload={"query_id": "Q1"})]
    cache.put("k1", _final(), events)

    hit = cache.get("k1")
    assert hit is not None
    assert hit.final_response.answer_markdown.startswith("jawaban")
    assert len(hit.trace_events) == 1
    assert hit.trace_events[0].event_type == "query_started"
    assert hit.age_seconds < 5


def test_get_returns_none_on_miss(tmp_path: Path) -> None:
    cache = AnswerCache(tmp_path / "cache.db")
    assert cache.get("no-such-key") is None


def test_ttl_expired_returns_none(tmp_path: Path) -> None:
    cache = AnswerCache(tmp_path / "cache.db", ttl_seconds=0)
    cache.put("k1", _final(), [])
    # ttl_seconds=0 means "anything older than 0s is stale" → immediate miss.
    time.sleep(0.01)
    assert cache.get("k1") is None
    # Stale entry should be purged — put-after-miss works cleanly.
    assert cache.stats()["count"] == 0


def test_cacheable_refusal_persists(tmp_path: Path) -> None:
    cache = AnswerCache(tmp_path / "cache.db")
    cache.put("k-silent", _final(RefusalReason.CORPUS_SILENT), [])
    assert cache.get("k-silent") is not None


def test_uncacheable_refusal_is_dropped(tmp_path: Path) -> None:
    cache = AnswerCache(tmp_path / "cache.db")
    cache.put("k-budget", _final(RefusalReason.RETRIEVAL_BUDGET_EXHAUSTED), [])
    cache.put("k-verify", _final(RefusalReason.CITATIONS_UNVERIFIABLE), [])
    assert cache.get("k-budget") is None
    assert cache.get("k-verify") is None


def test_clear_wipes_entries(tmp_path: Path) -> None:
    cache = AnswerCache(tmp_path / "cache.db")
    cache.put("k1", _final(), [])
    cache.put("k2", _final(), [])
    assert cache.stats()["count"] == 2
    removed = cache.clear()
    assert removed == 2
    assert cache.stats()["count"] == 0


# ---------------------------------------------------------------------------
# Orchestrator short-circuit
# ---------------------------------------------------------------------------


def _orch(cache, *, drafter_calls_expected: int) -> tuple[Orchestrator, FakeDrafter, FakeVerifier]:
    normalizer = FakeNormalizer(make_normalized())
    retriever = FakeRetriever(script=[[make_chunk()]])
    drafter = FakeDrafter(script=[drafter_answer()] * max(1, drafter_calls_expected))
    verifier = FakeVerifier(script=[verification_all_supported()])
    return (
        Orchestrator(
            normalizer=normalizer,
            retriever=retriever,
            drafter=drafter,
            verifier=verifier,
            limits=BudgetLimits(),
            cache=cache,
        ),
        drafter,
        verifier,
    )


@pytest.mark.asyncio
async def test_second_identical_query_is_served_from_cache(tmp_path: Path) -> None:
    cache = AnswerCache(tmp_path / "cache.db")
    orch1, drafter1, verifier1 = _orch(cache, drafter_calls_expected=1)
    state1 = await orch1.run("DBD anak derajat 2")
    assert state1.final_response is not None
    assert state1.final_response.from_cache is False
    assert drafter1.calls == 1
    assert verifier1.calls == 1

    # Second call — byte-identical (modulo case/whitespace) raw query
    # → cache hit, no Normalizer/Drafter/Verifier work.
    orch2, drafter2, verifier2 = _orch(cache, drafter_calls_expected=0)
    state2 = await orch2.run("  DBD   ANAK Derajat 2  ")
    assert state2.final_response is not None
    assert state2.final_response.from_cache is True
    assert state2.final_response.cached_age_s is not None
    assert drafter2.calls == 0
    assert verifier2.calls == 0

    # cache_hit trace must be present.
    cache_hits = [e for e in state2.trace_events if e.event_type == "cache_hit"]
    assert len(cache_hits) == 1


@pytest.mark.asyncio
async def test_cache_hit_skips_the_normalizer(tmp_path: Path) -> None:
    """Since the cache key is the raw query, hits bypass every LLM call
    including Haiku normalization — biggest speed win."""
    cache = AnswerCache(tmp_path / "cache.db")
    orch1, _, _ = _orch(cache, drafter_calls_expected=1)
    await orch1.run("TB paru dewasa rejimen OAT")

    # Second orchestrator with a normalizer that would raise if called.
    class ExplodingNormalizer:
        calls = 0

        async def run(self, state, *, prior_turn=None):  # type: ignore[no-untyped-def]
            ExplodingNormalizer.calls += 1
            raise AssertionError("Normalizer must not be called on cache hit")

    from tests.fakes import FakeDrafter, FakeRetriever, FakeVerifier

    orch2 = Orchestrator(
        normalizer=ExplodingNormalizer(),
        retriever=FakeRetriever(script=[[make_chunk()]]),
        drafter=FakeDrafter(script=[drafter_answer()]),
        verifier=FakeVerifier(script=[verification_all_supported()]),
        limits=BudgetLimits(),
        cache=cache,
    )
    state2 = await orch2.run("TB paru dewasa rejimen OAT")
    assert state2.final_response is not None
    assert state2.final_response.from_cache is True
    assert ExplodingNormalizer.calls == 0


@pytest.mark.asyncio
async def test_cache_miss_still_calls_agents(tmp_path: Path) -> None:
    cache = AnswerCache(tmp_path / "cache.db")
    orch, drafter, verifier = _orch(cache, drafter_calls_expected=1)
    state = await orch.run("DBD anak derajat 2")
    assert drafter.calls == 1
    assert verifier.calls == 1
    assert state.final_response is not None
    assert state.final_response.from_cache is False


@pytest.mark.asyncio
async def test_cache_preserves_new_query_id_on_replay(tmp_path: Path) -> None:
    cache = AnswerCache(tmp_path / "cache.db")
    orch1, _, _ = _orch(cache, drafter_calls_expected=1)
    state1 = await orch1.run("DBD anak derajat 2")

    orch2, _, _ = _orch(cache, drafter_calls_expected=0)
    state2 = await orch2.run("DBD anak derajat 2")

    assert state2.final_response is not None
    # query_id on replay must match the NEW state's query_id, not the
    # stored one — SSE handlers key queues on state.query_id.
    assert state2.final_response.query_id == state2.query_id
    assert state1.query_id != state2.query_id
