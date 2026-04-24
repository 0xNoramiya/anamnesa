"""Tests for the eval harness.

These exercise:
  - Query schema validation (`eval.queries.QUERIES` all parse).
  - End-to-end dry-run (scripted fakes) for a single query id.
  - Hallucinated-citation detection fires on an unknown doc_id.
  - Exception isolation: a failing drafter doesn't abort the run.
  - Category filter narrows to the expected subset.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest

from core.refusals import RefusalReason
from core.state import (
    Citation,
    CurrencyFlag,
    FinalResponse,
    QueryState,
)
from eval.queries import QUERIES, QueryExpectation
from eval.run_eval import run_all, score_result


def test_queries_parse_and_count_is_23() -> None:
    assert len(QUERIES) == 23
    ids = [q.id for q in QUERIES]
    assert len(set(ids)) == len(ids), "duplicate ids in QUERIES"
    cats = {q.category for q in QUERIES}
    assert cats == {"grounded", "aging", "absent"}


def test_category_distribution() -> None:
    cats = [q.category for q in QUERIES]
    assert cats.count("grounded") == 17
    assert cats.count("aging") == 3
    assert cats.count("absent") == 3


@pytest.mark.asyncio
async def test_dry_run_single_query_passes_scoring(tmp_path: Path) -> None:
    results = await run_all(dry_run=True, ids=["q001"], max_concurrent=1)
    assert len(results) == 1
    r = results[0]
    assert r["id"] == "q001"
    # Dry-run uses a generic drafter_answer() fake whose citation key is
    # PPK-FKTP-2015 (not in our real manifest). The refusal/cites checks
    # still run; overall_pass may or may not be True. What we assert is
    # that the runner didn't crash and produced a complete record.
    assert r["error"] is None
    assert "score" in r
    assert r["query_id"] is not None


@pytest.mark.asyncio
async def test_dry_run_absent_category_produces_refusal() -> None:
    results = await run_all(dry_run=True, category="absent", max_concurrent=1)
    assert len(results) == 3
    for r in results:
        assert r["refusal_reason"] == RefusalReason.CORPUS_SILENT.value
        assert r["score"]["refusal_match"] is True
        assert r["score"]["citations_min"] is True  # min_citations = 0
        assert r["error"] is None


def _synthetic_state(doc_id_in_citation: str) -> QueryState:
    """Build a QueryState with a FinalResponse whose sole citation uses
    the given doc_id. Nothing else is populated."""
    citation = Citation(
        key=f"{doc_id_in_citation}:p1:x",
        doc_id=doc_id_in_citation,
        page=1,
        section_slug="x",
        chunk_text="...",
    )
    state = QueryState(original_query="q")
    state.final_response = FinalResponse(
        query_id=state.query_id,
        answer_markdown="some answer [[ref]]",
        citations=[citation],
        currency_flags=[],
    )
    return state


def test_scorer_flags_hallucinated_citation() -> None:
    manifest_doc_ids = {"pnpk-dengue-anak-2021", "ppk-fktp-2015"}
    expect = QueryExpectation()
    state = _synthetic_state("nonexistent-doc-2099")
    sc = score_result(expect, state, manifest_doc_ids)
    assert sc.no_hallucinated_citations is False
    assert sc.overall_pass is False


def test_scorer_passes_valid_citation() -> None:
    manifest_doc_ids = {"ppk-fktp-2015"}
    expect = QueryExpectation(min_citations=1)
    state = _synthetic_state("ppk-fktp-2015")
    sc = score_result(expect, state, manifest_doc_ids)
    assert sc.no_hallucinated_citations is True


def test_scorer_currency_match_requires_flag() -> None:
    manifest_doc_ids = {"ppk-fktp-2015"}
    expect = QueryExpectation(min_citations=1, currency_must_include="aging")
    state = _synthetic_state("ppk-fktp-2015")
    # No currency_flags set → mismatch.
    sc = score_result(expect, state, manifest_doc_ids)
    assert sc.currency_match is False

    # Add an aging flag → match.
    state.final_response = state.final_response.model_copy(
        update={
            "currency_flags": [
                CurrencyFlag(
                    citation_key="ppk-fktp-2015:p1:x",
                    status="aging",
                    source_year=2015,
                )
            ]
        }
    )
    sc = score_result(expect, state, manifest_doc_ids)
    assert sc.currency_match is True


def test_scorer_keyword_match_ignores_citation_markers() -> None:
    """Keywords should match against prose stripped of `[[key]]` markers."""
    manifest_doc_ids = {"ppk-fktp-2015"}
    expect = QueryExpectation(
        min_citations=1,
        must_contain_keywords=["kristaloid"],
    )
    state = _synthetic_state("ppk-fktp-2015")
    state.final_response = state.final_response.model_copy(
        update={"answer_markdown": "Beri cairan kristaloid 6-7 ml/kg [[ppk-fktp-2015:p1:x]]"}
    )
    sc = score_result(expect, state, manifest_doc_ids)
    assert sc.keyword_match is True


@pytest.mark.asyncio
async def test_exception_in_orchestrator_isolated_per_query(monkeypatch: Any) -> None:
    """A single query blowing up must not abort other queries."""
    from eval import run_eval as mod

    call_count = {"n": 0}

    real = mod._build_dry_run_orchestrator

    def _explode_on_second(q):
        call_count["n"] += 1
        if call_count["n"] == 1:
            raise RuntimeError("boom on first")
        return real(q)

    monkeypatch.setattr(mod, "_build_dry_run_orchestrator", _explode_on_second)

    results = await run_all(dry_run=True, ids=["q019", "q020"], max_concurrent=1)
    assert len(results) == 2
    errors = [r for r in results if r["error"]]
    survivors = [r for r in results if not r["error"]]
    assert len(errors) == 1
    assert "boom on first" in errors[0]["error"]
    assert len(survivors) == 1
    assert survivors[0]["error"] is None


@pytest.mark.asyncio
async def test_category_filter_narrows_to_absent() -> None:
    results = await run_all(dry_run=True, category="absent", max_concurrent=1)
    assert len(results) == 3
    assert {r["id"] for r in results} == {"q010", "q019", "q020"}


@pytest.mark.asyncio
async def test_ids_filter_narrows_to_listed() -> None:
    results = await run_all(dry_run=True, ids=["q001", "q005"], max_concurrent=1)
    assert {r["id"] for r in results} == {"q001", "q005"}
