"""Live round-trip: run a query twice against the real orchestrator with
the cache enabled. Confirm the second call is sub-second and populated
from cache.
"""

from __future__ import annotations

import asyncio
import os
import time
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()

QUERY = "Pasien TB paru dewasa baru BTA positif. Rejimen OAT lini pertama dan durasi?"


async def main() -> None:
    from agents.drafter import OpusDrafter
    from agents.normalizer import HaikuNormalizer
    from agents.verifier import OpusVerifier
    from core.budget import BudgetLimits
    from core.cache import AnswerCache
    from core.orchestrator import Orchestrator
    from core.retrieval import default_retriever
    from mcp.client import LocalRetriever

    api_key = os.environ["ANTHROPIC_API_KEY"]
    os.environ.setdefault("ANAMNESA_EMBEDDER", "bge")

    cache_db = Path("/tmp/anamnesa_probe_cache.db")
    cache_db.unlink(missing_ok=True)  # noqa: ASYNC240 — one-off probe, not a server path
    cache = AnswerCache(cache_db)

    hybrid = default_retriever()
    retriever = LocalRetriever(retriever=hybrid)
    orch = Orchestrator(
        normalizer=HaikuNormalizer(model_id="claude-haiku-4-5-20251001", api_key=api_key),
        retriever=retriever,
        drafter=OpusDrafter(
            model_id="claude-opus-4-7", api_key=api_key, retriever=retriever, effort="high"
        ),
        verifier=OpusVerifier(
            model_id="claude-opus-4-7", api_key=api_key, retriever=retriever, effort="high"
        ),
        limits=BudgetLimits.from_env(),
        cache=cache,
    )

    for label in ("first (live)", "second (should be cache hit)"):
        print(f"\n--- {label} ---")
        t0 = time.perf_counter()
        state = await orch.run(QUERY)
        wall = time.perf_counter() - t0
        fr = state.final_response
        print(f"wall:       {wall:.2f}s")
        print(f"from_cache: {fr.from_cache if fr else '?'}")
        print(f"age_s:      {fr.cached_age_s if fr else '?'}")
        print(f"citations:  {len(fr.citations) if fr else 0}")
        print(f"refusal:    {fr.refusal_reason.value if fr and fr.refusal_reason else None}")

    print(f"\ncache stats: {cache.stats()}")
    cache.close()


if __name__ == "__main__":
    asyncio.run(main())
