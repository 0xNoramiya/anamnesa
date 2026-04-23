"""Live probe: real OpusDrafter with the new streaming code against a
real retrieval. Measure time-to-first-token and total.
"""

from __future__ import annotations

import asyncio
import os
import sys
import time

from dotenv import load_dotenv

load_dotenv()

from agents.drafter import OpusDrafter
from core.retrieval import default_retriever
from core.state import NormalizedQuery, QueryState, RetrievalFilters
from mcp.client import LocalRetriever


async def main() -> None:
    api_key = os.environ["ANTHROPIC_API_KEY"]
    hybrid = default_retriever()
    retriever = LocalRetriever(retriever=hybrid)

    nq = NormalizedQuery(
        structured_query="Langkah resusitasi awal neonatus 60 detik pertama apnea HR<100",
        intent="tatalaksana",
        patient_context="pediatric",
        condition_tags=["asfiksia_neonatorum"],
        keywords_id=["resusitasi", "neonatus", "apnea"],
        keywords_en=["neonatal", "resuscitation", "golden minute"],
    )
    state = QueryState(original_query="Resusitasi neonatus 60 detik pertama?")
    state.normalized_query = nq

    attempt = await retriever.search(nq, RetrievalFilters(), attempt_num=1)
    state.append_retrieval(attempt)

    drafter = OpusDrafter(
        model_id="claude-opus-4-7",
        api_key=api_key,
        retriever=retriever,
        effort="medium",
        thinking_budget=0,  # adaptive thinking batches output → kills streaming
    )

    # Poll trace_events from a second task so we can watch deltas
    # stream in real time. Pydantic locks down __setattr__ so we can't
    # just monkey-patch state.append_trace.
    first_delta_at: float | None = None
    chars_printed = 0
    t0 = time.perf_counter()

    async def printer():
        nonlocal first_delta_at, chars_printed
        seen = 0
        while True:
            evs = state.trace_events
            while seen < len(evs):
                ev = evs[seen]
                seen += 1
                if ev.agent == "drafter" and ev.event_type == "text_delta":
                    if first_delta_at is None:
                        first_delta_at = time.perf_counter() - t0
                        print(f"\n[first delta at {first_delta_at:.1f}s]\n", file=sys.stderr)
                    chunk = ev.payload.get("text", "")
                    sys.stdout.write(chunk)
                    sys.stdout.flush()
                    chars_printed += len(chunk)
            await asyncio.sleep(0.05)

    printer_task = asyncio.create_task(printer())
    result = await drafter.run(state)
    printer_task.cancel()
    # One final drain — anything that landed between the last poll and now.
    for ev in state.trace_events:
        if ev.agent == "drafter" and ev.event_type == "text_delta":
            pass  # already printed via the poller
    total = time.perf_counter() - t0
    print(f"\n\n--- done ---", file=sys.stderr)
    print(f"total wall:     {total:.1f}s", file=sys.stderr)
    if first_delta_at:
        print(f"first delta:    {first_delta_at:.1f}s", file=sys.stderr)
    print(f"chars streamed: {chars_printed}", file=sys.stderr)
    print(f"decision:       {type(result).__name__}", file=sys.stderr)


if __name__ == "__main__":
    os.environ.setdefault("ANAMNESA_EMBEDDER", "bge")
    asyncio.run(main())
