"""Orchestrator control-loop tests.

These tests cover every branch in the control loop specified in
CLAUDE.md > "Control loop" and "Refusal is always a valid terminal state".
"""

from __future__ import annotations

import pytest

from core.budget import BudgetLimits
from core.orchestrator import Orchestrator
from core.refusals import RefusalReason
from core.state import FinalResponse, RetrievalFilters
from tests.fakes import (
    FakeDrafter,
    FakeNormalizer,
    FakeRetriever,
    FakeVerifier,
    drafter_answer,
    drafter_need_more,
    drafter_refuse,
    make_chunk,
    make_normalized,
    normalizer_refusal,
    verification_all_supported,
    verification_unsupported,
)


def _orchestrator(
    *,
    normalizer,
    drafter,
    verifier,
    retriever,
    limits: BudgetLimits | None = None,
) -> Orchestrator:
    return Orchestrator(
        normalizer=normalizer,
        retriever=retriever,
        drafter=drafter,
        verifier=verifier,
        limits=limits or BudgetLimits(),
    )


@pytest.mark.asyncio
async def test_happy_path_returns_final_response_with_citations() -> None:
    normalizer = FakeNormalizer(make_normalized())
    retriever = FakeRetriever(script=[[make_chunk()]])
    drafter = FakeDrafter(script=[drafter_answer()])
    verifier = FakeVerifier(script=[verification_all_supported()])

    orch = _orchestrator(
        normalizer=normalizer, drafter=drafter, verifier=verifier, retriever=retriever
    )
    state = await orch.run("DBD anak derajat 2, tata laksana cairan awal?")

    assert state.final_response is not None
    assert state.refusal_reason is None
    assert state.final_response.refusal_reason is None
    assert len(state.final_response.citations) == 1
    assert state.final_response.currency_flags  # currency attached
    assert drafter.calls == 1
    assert verifier.calls == 1
    assert len(retriever.calls) == 1


@pytest.mark.asyncio
async def test_normalizer_refusal_short_circuits_everything() -> None:
    normalizer = FakeNormalizer(normalizer_refusal(RefusalReason.OUT_OF_MEDICAL_SCOPE))
    retriever = FakeRetriever(script=[[make_chunk()]])
    drafter = FakeDrafter(script=[])
    verifier = FakeVerifier(script=[])

    orch = _orchestrator(
        normalizer=normalizer, drafter=drafter, verifier=verifier, retriever=retriever
    )
    state = await orch.run("resep nasi goreng?")

    assert state.refusal_reason is RefusalReason.OUT_OF_MEDICAL_SCOPE
    assert state.final_response is not None
    assert state.final_response.refusal_reason is RefusalReason.OUT_OF_MEDICAL_SCOPE
    assert drafter.calls == 0
    assert verifier.calls == 0
    assert len(retriever.calls) == 0


@pytest.mark.asyncio
async def test_drafter_requests_more_retrieval_then_answers() -> None:
    normalizer = FakeNormalizer(make_normalized())
    retriever = FakeRetriever(script=[[], [make_chunk()]])
    drafter = FakeDrafter(
        script=[
            drafter_need_more(feedback="empty result set, narrow to ppk_fktp"),
            drafter_answer(),
        ]
    )
    verifier = FakeVerifier(script=[verification_all_supported()])

    orch = _orchestrator(
        normalizer=normalizer, drafter=drafter, verifier=verifier, retriever=retriever
    )
    state = await orch.run("DBD anak derajat 2")

    assert state.final_response is not None
    assert state.refusal_reason is None
    assert drafter.calls == 2
    assert len(retriever.calls) == 2
    # 2nd retrieval filters came from the Drafter's hint
    assert retriever.calls[1].conditions == ["dengue"]


@pytest.mark.asyncio
async def test_drafter_refusal_propagates_to_final_response() -> None:
    normalizer = FakeNormalizer(make_normalized())
    retriever = FakeRetriever(script=[[]])
    drafter = FakeDrafter(script=[drafter_refuse(RefusalReason.CORPUS_SILENT)])
    verifier = FakeVerifier(script=[])

    orch = _orchestrator(
        normalizer=normalizer, drafter=drafter, verifier=verifier, retriever=retriever
    )
    state = await orch.run("kondisi yang tidak ada di katalog")

    assert state.refusal_reason is RefusalReason.CORPUS_SILENT
    assert state.final_response is not None
    assert state.final_response.refusal_reason is RefusalReason.CORPUS_SILENT
    assert verifier.calls == 0


@pytest.mark.asyncio
async def test_retrieval_budget_exhausted_when_drafter_keeps_asking() -> None:
    normalizer = FakeNormalizer(make_normalized())
    retriever = FakeRetriever(script=[[], [], []])
    # Drafter asks for narrower retrieval every time; it never gets to answer.
    drafter = FakeDrafter(
        script=[drafter_need_more(), drafter_need_more(), drafter_need_more()]
    )
    verifier = FakeVerifier(script=[])

    orch = _orchestrator(
        normalizer=normalizer,
        drafter=drafter,
        verifier=verifier,
        retriever=retriever,
        limits=BudgetLimits(max_retrieval_attempts=3, max_drafter_calls=3),
    )
    state = await orch.run("apa pun")

    assert state.refusal_reason is RefusalReason.RETRIEVAL_BUDGET_EXHAUSTED
    assert len(retriever.calls) == 3


@pytest.mark.asyncio
async def test_verifier_rejects_then_drafter_revises_successfully() -> None:
    normalizer = FakeNormalizer(make_normalized())
    retriever = FakeRetriever(script=[[make_chunk()], [make_chunk(page=413)]])
    drafter = FakeDrafter(script=[drafter_answer(), drafter_answer()])
    verifier = FakeVerifier(
        script=[verification_unsupported("c1 not grounded"), verification_all_supported()]
    )

    orch = _orchestrator(
        normalizer=normalizer, drafter=drafter, verifier=verifier, retriever=retriever
    )
    state = await orch.run("q")

    assert state.final_response is not None
    assert state.refusal_reason is None
    assert drafter.calls == 2
    assert verifier.calls == 2
    # 2nd drafter call received the verifier's feedback
    assert drafter.last_feedback == "c1 not grounded"


@pytest.mark.asyncio
async def test_verifier_rejects_twice_triggers_refusal() -> None:
    normalizer = FakeNormalizer(make_normalized())
    retriever = FakeRetriever(script=[[make_chunk()], [make_chunk()]])
    drafter = FakeDrafter(script=[drafter_answer(), drafter_answer()])
    verifier = FakeVerifier(
        script=[verification_unsupported(), verification_unsupported()]
    )

    orch = _orchestrator(
        normalizer=normalizer, drafter=drafter, verifier=verifier, retriever=retriever
    )
    state = await orch.run("q")

    assert state.refusal_reason is RefusalReason.CITATIONS_UNVERIFIABLE
    assert state.final_response is not None
    assert state.final_response.refusal_reason is RefusalReason.CITATIONS_UNVERIFIABLE


@pytest.mark.asyncio
async def test_trace_events_populated_for_every_agent_invocation() -> None:
    normalizer = FakeNormalizer(make_normalized())
    retriever = FakeRetriever(script=[[make_chunk()]])
    drafter = FakeDrafter(script=[drafter_answer()])
    verifier = FakeVerifier(script=[verification_all_supported()])

    orch = _orchestrator(
        normalizer=normalizer, drafter=drafter, verifier=verifier, retriever=retriever
    )
    state = await orch.run("DBD anak")

    agents_seen = {e.agent for e in state.trace_events}
    assert {"orchestrator", "normalizer", "retriever", "drafter", "verifier"} <= agents_seen
    assert any(e.event_type == "query_started" for e in state.trace_events)
    assert any(e.event_type == "query_completed" for e in state.trace_events)


@pytest.mark.asyncio
async def test_currency_flags_flow_from_verifier_to_final() -> None:
    normalizer = FakeNormalizer(make_normalized())
    retriever = FakeRetriever(script=[[make_chunk()]])
    drafter = FakeDrafter(script=[drafter_answer()])
    verifier = FakeVerifier(script=[verification_all_supported()])

    orch = _orchestrator(
        normalizer=normalizer, drafter=drafter, verifier=verifier, retriever=retriever
    )
    state = await orch.run("q")

    assert state.final_response is not None
    flags = state.final_response.currency_flags
    assert len(flags) == 1
    assert flags[0].status == "aging"
    assert flags[0].citation_key == "PPK-FKTP-2015:p412:dbd_tata_laksana"


class _ExplodingDrafter:
    async def run(self, state, *, verifier_feedback=None):
        raise RuntimeError("boom")


@pytest.mark.asyncio
async def test_agent_exceptions_are_not_swallowed() -> None:
    normalizer = FakeNormalizer(make_normalized())
    retriever = FakeRetriever(script=[[make_chunk()]])
    verifier = FakeVerifier(script=[])

    orch = _orchestrator(
        normalizer=normalizer,
        drafter=_ExplodingDrafter(),
        verifier=verifier,
        retriever=retriever,
    )
    with pytest.raises(RuntimeError, match="boom"):
        await orch.run("q")


@pytest.mark.asyncio
async def test_final_response_contains_query_id_matching_state() -> None:
    normalizer = FakeNormalizer(make_normalized())
    retriever = FakeRetriever(script=[[make_chunk()]])
    drafter = FakeDrafter(script=[drafter_answer()])
    verifier = FakeVerifier(script=[verification_all_supported()])

    orch = _orchestrator(
        normalizer=normalizer, drafter=drafter, verifier=verifier, retriever=retriever
    )
    state = await orch.run("q")

    assert isinstance(state.final_response, FinalResponse)
    assert state.final_response.query_id == state.query_id


@pytest.mark.asyncio
async def test_first_retrieval_uses_default_filters() -> None:
    normalizer = FakeNormalizer(make_normalized())
    retriever = FakeRetriever(script=[[make_chunk()]])
    drafter = FakeDrafter(script=[drafter_answer()])
    verifier = FakeVerifier(script=[verification_all_supported()])

    orch = _orchestrator(
        normalizer=normalizer, drafter=drafter, verifier=verifier, retriever=retriever
    )
    await orch.run("q")

    assert isinstance(retriever.calls[0], RetrievalFilters)
    assert retriever.calls[0].top_k == 10
    assert retriever.calls[0].doc_ids is None
