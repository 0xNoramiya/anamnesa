"""Tests for the "why refused" hint — FinalResponse.retrieval_preview
should surface near-miss chunks on corpus-silent refusals but stay
empty on out-of-scope / patient-specific / success paths."""

from __future__ import annotations

import pytest

from core.budget import BudgetLimits
from core.orchestrator import Orchestrator
from core.refusals import RefusalReason
from tests.fakes import (
    FakeDrafter,
    FakeNormalizer,
    FakeRetriever,
    FakeVerifier,
    drafter_answer,
    drafter_refuse,
    make_chunk,
    make_normalized,
    normalizer_refusal,
    verification_all_supported,
)


def _orch(normalizer, retriever, drafter, verifier) -> Orchestrator:
    return Orchestrator(
        normalizer=normalizer,
        retriever=retriever,
        drafter=drafter,
        verifier=verifier,
        limits=BudgetLimits(),
    )


@pytest.mark.asyncio
async def test_corpus_silent_refusal_surfaces_top_chunks() -> None:
    """When the Drafter refuses because the retrieval was a near-miss,
    the user should see the chunks Anamnesa did find — so they can check
    for themselves that the corpus was searched, not that the app broke."""
    chunks = [
        make_chunk(doc_id="ppk-fktp-2015", page=412),
        make_chunk(doc_id="pnpk-tb-2019", page=88),
        make_chunk(doc_id="pnpk-dbd-anak-2014", page=23),
    ]
    orch = _orch(
        normalizer=FakeNormalizer(make_normalized()),
        retriever=FakeRetriever(script=[chunks]),
        drafter=FakeDrafter(script=[drafter_refuse(RefusalReason.CORPUS_SILENT)]),
        verifier=FakeVerifier(script=[]),
    )
    state = await orch.run("something niche the corpus can't answer")
    fr = state.final_response
    assert fr is not None
    assert fr.refusal_reason == RefusalReason.CORPUS_SILENT
    assert len(fr.retrieval_preview) == 3
    # Preserves chunk ordering from the retriever.
    assert [h.doc_id for h in fr.retrieval_preview] == [
        "ppk-fktp-2015",
        "pnpk-tb-2019",
        "pnpk-dbd-anak-2014",
    ]
    # Preview text is whitespace-collapsed and length-bounded.
    for hint in fr.retrieval_preview:
        assert "\n" not in hint.text_preview
        assert len(hint.text_preview) <= 220


@pytest.mark.asyncio
async def test_preview_caps_at_three_chunks() -> None:
    chunks = [make_chunk(doc_id=f"doc-{i}", page=i) for i in range(10)]
    orch = _orch(
        normalizer=FakeNormalizer(make_normalized()),
        retriever=FakeRetriever(script=[chunks]),
        drafter=FakeDrafter(script=[drafter_refuse(RefusalReason.CORPUS_SILENT)]),
        verifier=FakeVerifier(script=[]),
    )
    state = await orch.run("q")
    assert len(state.final_response.retrieval_preview) == 3


@pytest.mark.asyncio
async def test_out_of_scope_refusal_has_empty_preview() -> None:
    """Normalizer-side refusals never run retrieval. Previewing chunks
    that don't exist would be misleading — assert empty."""
    orch = _orch(
        normalizer=FakeNormalizer(
            normalizer_refusal(RefusalReason.OUT_OF_MEDICAL_SCOPE)
        ),
        retriever=FakeRetriever(script=[[make_chunk()]]),
        drafter=FakeDrafter(script=[]),
        verifier=FakeVerifier(script=[]),
    )
    state = await orch.run("what's the capital of France?")
    assert state.final_response.refusal_reason == RefusalReason.OUT_OF_MEDICAL_SCOPE
    assert state.final_response.retrieval_preview == []


@pytest.mark.asyncio
async def test_patient_specific_refusal_has_empty_preview() -> None:
    orch = _orch(
        normalizer=FakeNormalizer(make_normalized()),
        retriever=FakeRetriever(script=[[make_chunk()]]),
        drafter=FakeDrafter(
            script=[drafter_refuse(RefusalReason.PATIENT_SPECIFIC_REQUEST)]
        ),
        verifier=FakeVerifier(script=[]),
    )
    state = await orch.run("dosis yang harus saya berikan ke pasien saya")
    assert (
        state.final_response.refusal_reason
        == RefusalReason.PATIENT_SPECIFIC_REQUEST
    )
    assert state.final_response.retrieval_preview == []


@pytest.mark.asyncio
async def test_successful_answer_has_empty_preview() -> None:
    """Preview is a consolation for refusals only — successful answers
    carry their grounding in .citations."""
    orch = _orch(
        normalizer=FakeNormalizer(make_normalized()),
        retriever=FakeRetriever(script=[[make_chunk()]]),
        drafter=FakeDrafter(script=[drafter_answer()]),
        verifier=FakeVerifier(script=[verification_all_supported()]),
    )
    state = await orch.run("DBD anak derajat 2, tata laksana cairan awal?")
    assert state.final_response.refusal_reason is None
    assert state.final_response.retrieval_preview == []


@pytest.mark.asyncio
async def test_preview_collapses_long_chunk_text() -> None:
    long_chunk = make_chunk(doc_id="long-doc")
    # Replace text with something long and whitespace-heavy
    long_text = ("Lorem ipsum   dolor\n\nsit amet. " * 30).strip()
    long_chunk = long_chunk.model_copy(update={"text": long_text})
    orch = _orch(
        normalizer=FakeNormalizer(make_normalized()),
        retriever=FakeRetriever(script=[[long_chunk]]),
        drafter=FakeDrafter(script=[drafter_refuse(RefusalReason.CORPUS_SILENT)]),
        verifier=FakeVerifier(script=[]),
    )
    state = await orch.run("q")
    preview = state.final_response.retrieval_preview[0].text_preview
    assert len(preview) <= 220
    assert preview.endswith("…")
    assert "\n" not in preview
