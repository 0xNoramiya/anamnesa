"""Eval runner — drive the orchestrator across `eval.queries.QUERIES`,
score each result, and emit JSON + markdown summaries.

Usage:
    python -m eval.run_eval                 # run all 20, live API
    python -m eval.run_eval --dry-run       # scripted fakes, no API cost
    python -m eval.run_eval --ids q001,q005
    python -m eval.run_eval --category absent
    python -m eval.run_eval --max-concurrent 2
    python -m eval.run_eval --output-json eval/results/run.json
    python -m eval.run_eval --output-md    eval/results/run.md

`--dry-run` uses `tests.fakes` so the runner's plumbing exercises without
burning Anthropic tokens.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import os
import sys
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import structlog
from dotenv import load_dotenv

from core.manifest import Manifest
from core.orchestrator import Orchestrator
from core.refusals import RefusalReason
from core.state import QueryState
from eval.queries import QUERIES, Category, EvalQuery, QueryExpectation

log = structlog.get_logger("anamnesa.eval")


# Rough cost estimation — input tokens charged at full rate (no cached-read split).
PRICES_PER_MTOK = {
    "haiku": {"in": 1.00, "out": 5.00},
    "opus": {"in": 5.00, "out": 25.00},
}


def _estimate_cost(cost_ledger: Any) -> float:
    """Estimate USD cost from the state's CostLedger. Rough — input tokens
    charged at full rate (we don't split cached reads here)."""
    haiku_in = cost_ledger.input_tokens.get("normalizer", 0)
    haiku_out = cost_ledger.output_tokens.get("normalizer", 0)
    opus_in = cost_ledger.input_tokens.get("drafter", 0) + cost_ledger.input_tokens.get(
        "verifier", 0
    )
    opus_out = cost_ledger.output_tokens.get("drafter", 0) + cost_ledger.output_tokens.get(
        "verifier", 0
    )
    cost = (
        haiku_in * PRICES_PER_MTOK["haiku"]["in"]
        + haiku_out * PRICES_PER_MTOK["haiku"]["out"]
        + opus_in * PRICES_PER_MTOK["opus"]["in"]
        + opus_out * PRICES_PER_MTOK["opus"]["out"]
    ) / 1_000_000
    return round(cost, 4)


@dataclass(frozen=True)
class Score:
    refusal_match: bool
    citations_min: bool
    source_type_match: bool | None  # None if the query didn't set the expectation
    doc_id_match: bool | None
    currency_match: bool | None
    keyword_match: bool | None
    no_hallucinated_citations: bool

    @property
    def overall_pass(self) -> bool:
        checks = [
            self.refusal_match,
            self.citations_min,
            self.no_hallucinated_citations,
        ]
        for opt in (
            self.source_type_match,
            self.doc_id_match,
            self.currency_match,
            self.keyword_match,
        ):
            if opt is not None:
                checks.append(opt)
        return all(checks)


def _citations_hallucinated(state: QueryState, manifest_doc_ids: set[str]) -> bool:
    """True iff ANY citation references a doc not in the manifest."""
    if state.final_response is None:
        return False
    for c in state.final_response.citations:
        if c.doc_id not in manifest_doc_ids:
            return True
    return False


def _strip_citations(text: str) -> str:
    """Strip `[[key]]` markers so keyword checks operate on prose only."""
    import re

    return re.sub(r"\[\[[^\]]+\]\]", "", text)


def score_result(
    expectation: QueryExpectation,
    state: QueryState,
    manifest_doc_ids: set[str],
) -> Score:
    fr = state.final_response
    actual_refusal = state.refusal_reason

    refusal_match = actual_refusal == expectation.refusal_reason

    num_cites = len(fr.citations) if fr else 0
    citations_min = num_cites >= expectation.min_citations

    source_type_match: bool | None
    if expectation.expected_source_types is not None:
        if fr is None or not fr.citations:
            source_type_match = False
        else:
            source_type_match = any(
                _doc_source_type(c.doc_id) in expectation.expected_source_types
                for c in fr.citations
            )
    else:
        source_type_match = None

    doc_id_match: bool | None
    if expectation.expected_doc_ids_any_of is not None:
        if fr is None or not fr.citations:
            doc_id_match = False
        else:
            cited = {c.doc_id for c in fr.citations}
            doc_id_match = bool(cited.intersection(expectation.expected_doc_ids_any_of))
    else:
        doc_id_match = None

    currency_match: bool | None
    if expectation.currency_must_include is not None:
        if fr is None or not fr.currency_flags:
            currency_match = False
        else:
            currency_match = any(
                f.status == expectation.currency_must_include for f in fr.currency_flags
            )
    else:
        currency_match = None

    keyword_match: bool | None
    if expectation.must_contain_keywords:
        if fr is None:
            keyword_match = False
        else:
            answer = _strip_citations(fr.answer_markdown).lower()
            keyword_match = all(
                kw.lower() in answer for kw in expectation.must_contain_keywords
            )
    else:
        keyword_match = None

    no_hallucinated = not _citations_hallucinated(state, manifest_doc_ids)

    return Score(
        refusal_match=refusal_match,
        citations_min=citations_min,
        source_type_match=source_type_match,
        doc_id_match=doc_id_match,
        currency_match=currency_match,
        keyword_match=keyword_match,
        no_hallucinated_citations=no_hallucinated,
    )


_MANIFEST_CACHE: dict[str, tuple[set[str], dict[str, str]]] = {}


def _manifest_doc_ids_and_types() -> tuple[set[str], dict[str, str]]:
    path = Path("catalog/manifest.json")
    key = str(path.resolve())
    cached = _MANIFEST_CACHE.get(key)
    if cached is not None:
        return cached
    if not path.exists():
        result: tuple[set[str], dict[str, str]] = (set(), {})
        _MANIFEST_CACHE[key] = result
        return result
    m = Manifest.model_validate_json(path.read_text(encoding="utf-8"))
    ids = {d.doc_id for d in m.documents}
    types = {d.doc_id: d.source_type for d in m.documents}
    _MANIFEST_CACHE[key] = (ids, types)
    return ids, types


def _doc_source_type(doc_id: str) -> str:
    _, types = _manifest_doc_ids_and_types()
    return types.get(doc_id, "unknown")


def _build_live_orchestrator() -> Orchestrator:
    """Mirror scripts/run_query.py exactly."""
    from agents.drafter import OpusDrafter
    from agents.normalizer import HaikuNormalizer
    from agents.verifier import OpusVerifier
    from core.budget import BudgetLimits
    from core.retrieval import default_retriever
    from mcp.client import LocalRetriever

    api_key = os.getenv("ANTHROPIC_API_KEY")
    if not api_key:
        raise RuntimeError("ANTHROPIC_API_KEY not set — copy .env.example to .env.")

    retriever = LocalRetriever(retriever=default_retriever())
    return Orchestrator(
        normalizer=HaikuNormalizer(
            model_id=os.getenv("ANAMNESA_MODEL_NORMALIZER", "claude-haiku-4-5-20251001"),
            api_key=api_key,
        ),
        retriever=retriever,
        drafter=OpusDrafter(
            model_id=os.getenv("ANAMNESA_MODEL_DRAFTER", "claude-opus-4-7"),
            api_key=api_key,
            retriever=retriever,
            thinking_budget=int(os.getenv("ANAMNESA_DRAFTER_THINKING_BUDGET", 8000)),
        ),
        verifier=OpusVerifier(
            model_id=os.getenv("ANAMNESA_MODEL_VERIFIER", "claude-opus-4-7"),
            api_key=api_key,
            retriever=retriever,
            thinking_budget=int(os.getenv("ANAMNESA_VERIFIER_THINKING_BUDGET", 12000)),
        ),
        limits=BudgetLimits.from_env(),
    )


def _build_dry_run_orchestrator(query: EvalQuery) -> Orchestrator:
    """Scripted fakes that satisfy each category's expectation trivially."""
    from core.budget import BudgetLimits
    from tests.fakes import (
        FakeDrafter,
        FakeNormalizer,
        FakeRetriever,
        FakeVerifier,
        drafter_answer,
        drafter_refuse,
        make_chunk,
        make_normalized,
        verification_all_supported,
    )

    normalizer = FakeNormalizer(make_normalized(query.query))
    retriever = FakeRetriever(script=[[make_chunk()]])
    if query.category == "absent":
        drafter = FakeDrafter(script=[drafter_refuse(RefusalReason.CORPUS_SILENT)])
        verifier = FakeVerifier(script=[])
    else:
        drafter = FakeDrafter(script=[drafter_answer()])
        verifier = FakeVerifier(script=[verification_all_supported()])
    return Orchestrator(
        normalizer=normalizer,
        retriever=retriever,
        drafter=drafter,
        verifier=verifier,
        limits=BudgetLimits(),
    )


async def run_one(
    query: EvalQuery,
    *,
    dry_run: bool,
    manifest_doc_ids: set[str],
) -> dict[str, Any]:
    log.info("eval.query_started", id=query.id, category=query.category)
    t0 = datetime.now(UTC)
    try:
        orch = (
            _build_dry_run_orchestrator(query)
            if dry_run
            else _build_live_orchestrator()
        )
        state = await orch.run(query.query)
        sc = score_result(query.expected, state, manifest_doc_ids)
        fr = state.final_response
        result = {
            "id": query.id,
            "category": query.category,
            "query": query.query,
            "query_id": state.query_id,
            "refusal_reason": state.refusal_reason.value if state.refusal_reason else None,
            "citations": [c.model_dump() for c in (fr.citations if fr else [])],
            "currency_flags": [f.model_dump() for f in (fr.currency_flags if fr else [])],
            "answer_markdown": fr.answer_markdown if fr else None,
            "wall_clock_ms": state.cost.wall_clock_ms,
            "tokens": {
                "normalizer_in": state.cost.input_tokens.get("normalizer", 0),
                "normalizer_out": state.cost.output_tokens.get("normalizer", 0),
                "drafter_in": state.cost.input_tokens.get("drafter", 0),
                "drafter_out": state.cost.output_tokens.get("drafter", 0),
                "verifier_in": state.cost.input_tokens.get("verifier", 0),
                "verifier_out": state.cost.output_tokens.get("verifier", 0),
            },
            "cost_estimate_usd": _estimate_cost(state.cost),
            "score": {
                "refusal_match": sc.refusal_match,
                "citations_min": sc.citations_min,
                "source_type_match": sc.source_type_match,
                "doc_id_match": sc.doc_id_match,
                "currency_match": sc.currency_match,
                "keyword_match": sc.keyword_match,
                "no_hallucinated_citations": sc.no_hallucinated_citations,
                "overall_pass": sc.overall_pass,
            },
            "error": None,
        }
        log.info(
            "eval.query_completed",
            id=query.id,
            overall_pass=sc.overall_pass,
            refusal=state.refusal_reason.value if state.refusal_reason else None,
            citations=len(fr.citations) if fr else 0,
            wall_clock_ms=state.cost.wall_clock_ms,
        )
        return result
    except Exception as exc:
        wall_ms = int((datetime.now(UTC) - t0).total_seconds() * 1000)
        log.exception("eval.query_failed", id=query.id)
        return {
            "id": query.id,
            "category": query.category,
            "query": query.query,
            "query_id": None,
            "refusal_reason": None,
            "citations": [],
            "currency_flags": [],
            "answer_markdown": None,
            "wall_clock_ms": wall_ms,
            "tokens": {},
            "cost_estimate_usd": 0.0,
            "score": {
                "refusal_match": False,
                "citations_min": False,
                "source_type_match": None,
                "doc_id_match": None,
                "currency_match": None,
                "keyword_match": None,
                "no_hallucinated_citations": True,  # n/a — no citations to hallucinate
                "overall_pass": False,
            },
            "error": f"{type(exc).__name__}: {exc}",
        }


async def run_all(
    *,
    dry_run: bool = False,
    ids: list[str] | None = None,
    category: Category | None = None,
    max_concurrent: int = 1,
) -> list[dict[str, Any]]:
    queries = list(QUERIES)
    if ids:
        queries = [q for q in queries if q.id in ids]
    if category:
        queries = [q for q in queries if q.category == category]

    manifest_doc_ids, _ = _manifest_doc_ids_and_types()

    sem = asyncio.Semaphore(max(1, min(max_concurrent, 3)))

    async def _guarded(q: EvalQuery) -> dict[str, Any]:
        async with sem:
            return await run_one(q, dry_run=dry_run, manifest_doc_ids=manifest_doc_ids)

    return await asyncio.gather(*(_guarded(q) for q in queries))


def summarize_markdown(results: list[dict[str, Any]], started_at: datetime) -> str:
    total = len(results)
    passed = sum(1 for r in results if r["score"]["overall_pass"])
    pct = (passed / total * 100) if total else 0.0

    by_cat: dict[str, tuple[int, int]] = {}
    for r in results:
        cat = r["category"]
        p, t = by_cat.get(cat, (0, 0))
        p += int(r["score"]["overall_pass"])
        t += 1
        by_cat[cat] = (p, t)

    total_cost = sum(r.get("cost_estimate_usd", 0.0) for r in results)
    wallclocks = [r["wall_clock_ms"] for r in results if r.get("wall_clock_ms")]
    mean_ms = int(sum(wallclocks) / len(wallclocks)) if wallclocks else 0
    hallucinated = sum(
        1 for r in results if not r["score"]["no_hallucinated_citations"]
    )

    lines = [
        f"# Anamnesa Eval — {started_at.isoformat()}",
        "",
        "## Summary",
        f"- Queries: {total} total, {passed} passed ({pct:.0f}%)",
        "- By category: "
        + ", ".join(f"{cat} {p}/{t}" for cat, (p, t) in sorted(by_cat.items())),
        f"- Total cost (est): ${total_cost:.3f}",
        f"- Mean wall-clock: {mean_ms/1000:.1f}s",
        f"- Hallucinated citations: **{hallucinated}**"
        + ("  ❌" if hallucinated else "  ✅"),
        "",
        "## Per-query",
        "",
        "| id | category | pass | refusal | cites | ms | $ | notes |",
        "|---|---|---|---|---|---|---|---|",
    ]
    for r in results:
        mark = "✅" if r["score"]["overall_pass"] else "❌"
        refusal = r["refusal_reason"] or "-"
        cites = len(r["citations"])
        ms = r.get("wall_clock_ms", 0)
        cost = r.get("cost_estimate_usd", 0.0)
        notes = []
        if r["error"]:
            notes.append(f"ERR: {r['error']}")
        if not r["score"]["no_hallucinated_citations"]:
            notes.append("HALLUCINATED CITATION")
        for k in ("refusal_match", "citations_min", "source_type_match", "doc_id_match",
                  "currency_match", "keyword_match"):
            v = r["score"].get(k)
            if v is False:
                notes.append(f"{k}=fail")
        notes_str = "; ".join(notes) if notes else "-"
        lines.append(
            f"| {r['id']} | {r['category']} | {mark} | {refusal} | {cites} | "
            f"{ms} | {cost:.3f} | {notes_str} |"
        )
    return "\n".join(lines) + "\n"


def _cli(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="python -m eval.run_eval",
        description="Run Anamnesa eval queries and score results.",
    )
    parser.add_argument("--dry-run", action="store_true",
                        help="Use scripted fakes — no Anthropic cost.")
    parser.add_argument("--ids", help="Comma-separated query ids (e.g. q001,q005)")
    parser.add_argument("--category", choices=["grounded", "aging", "absent"])
    parser.add_argument("--max-concurrent", type=int, default=1)
    parser.add_argument("--output-json", type=Path)
    parser.add_argument("--output-md", type=Path)
    args = parser.parse_args(argv)

    load_dotenv()

    ids = args.ids.split(",") if args.ids else None
    started = datetime.now(UTC)

    results = asyncio.run(
        run_all(
            dry_run=args.dry_run,
            ids=ids,
            category=args.category,
            max_concurrent=args.max_concurrent,
        )
    )
    summary_md = summarize_markdown(results, started)

    if args.output_json:
        args.output_json.parent.mkdir(parents=True, exist_ok=True)
        args.output_json.write_text(
            json.dumps(
                {"started_at": started.isoformat(), "results": results},
                ensure_ascii=False,
                indent=2,
            ),
            encoding="utf-8",
        )
    if args.output_md:
        args.output_md.parent.mkdir(parents=True, exist_ok=True)
        args.output_md.write_text(summary_md, encoding="utf-8")

    print(summary_md)
    failures = sum(1 for r in results if not r["score"]["overall_pass"])
    return 1 if failures > 0 else 0


if __name__ == "__main__":
    sys.exit(_cli())
