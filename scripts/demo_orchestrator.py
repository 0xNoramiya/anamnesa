"""End-to-end scaffold demo using scripted fakes — no API calls.

Exercises every branch of the orchestrator (happy path, drafter
re-retrieval, verifier retry, refusal) so you can eyeball the trace
output and confirm the wiring before real agents land.

    python -m scripts.demo_orchestrator
"""

from __future__ import annotations

import asyncio
import json
from typing import Any

from core.orchestrator import Orchestrator
from core.state import QueryState
from tests.fakes import (
    FakeDrafter,
    FakeNormalizer,
    FakeRetriever,
    FakeVerifier,
    drafter_answer,
    drafter_need_more,
    make_chunk,
    make_normalized,
    verification_all_supported,
    verification_unsupported,
)


def _render(label: str, state: QueryState) -> dict[str, Any]:
    return {
        "scenario": label,
        "query_id": state.query_id,
        "refusal_reason": state.refusal_reason.value if state.refusal_reason else None,
        "answer": state.final_response.answer_markdown if state.final_response else None,
        "citations": [c.key for c in (state.final_response.citations or [])]
        if state.final_response
        else [],
        "currency_flags": [
            {"key": f.citation_key, "status": f.status, "year": f.source_year}
            for f in (state.final_response.currency_flags if state.final_response else [])
        ],
        "trace": [
            {"agent": e.agent, "event": e.event_type, "payload": e.payload}
            for e in state.trace_events
        ],
    }


async def _scenario_happy_path() -> dict[str, Any]:
    orch = Orchestrator(
        normalizer=FakeNormalizer(make_normalized()),
        retriever=FakeRetriever(script=[[make_chunk()]]),
        drafter=FakeDrafter(script=[drafter_answer()]),
        verifier=FakeVerifier(script=[verification_all_supported()]),
    )
    state = await orch.run("DBD anak derajat 2, tata laksana cairan awal?")
    return _render("happy_path", state)


async def _scenario_retrieval_retry() -> dict[str, Any]:
    orch = Orchestrator(
        normalizer=FakeNormalizer(make_normalized()),
        retriever=FakeRetriever(script=[[], [make_chunk()]]),
        drafter=FakeDrafter(script=[drafter_need_more(), drafter_answer()]),
        verifier=FakeVerifier(script=[verification_all_supported()]),
    )
    state = await orch.run("DBD anak — narrow it down")
    return _render("drafter_requests_more_retrieval", state)


async def _scenario_verifier_retry() -> dict[str, Any]:
    orch = Orchestrator(
        normalizer=FakeNormalizer(make_normalized()),
        retriever=FakeRetriever(script=[[make_chunk()], [make_chunk(page=413)]]),
        drafter=FakeDrafter(script=[drafter_answer(), drafter_answer()]),
        verifier=FakeVerifier(
            script=[
                verification_unsupported("c1 not grounded — revise or refuse"),
                verification_all_supported(),
            ]
        ),
    )
    state = await orch.run("verifier_retry_scenario")
    return _render("verifier_rejects_then_supports", state)


async def main() -> None:
    scenarios = await asyncio.gather(
        _scenario_happy_path(),
        _scenario_retrieval_retry(),
        _scenario_verifier_retry(),
    )
    print(json.dumps(scenarios, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    asyncio.run(main())
