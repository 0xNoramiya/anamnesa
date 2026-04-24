"""CLI entry point — wire real agents to the orchestrator.

Loads `.env` at startup so `ANTHROPIC_API_KEY` and related config land in
the process environment without a shell source step.

Usage:
    python -m scripts.run_query "DBD anak derajat 2, cairan awal?"
"""

from __future__ import annotations

import asyncio
import json
import os
import sys

from dotenv import load_dotenv

load_dotenv()  # side effect: .env → os.environ; idempotent; safe if absent.

from agents.drafter import OpusDrafter
from agents.normalizer import HaikuNormalizer
from agents.verifier import OpusVerifier
from core.budget import BudgetLimits
from core.orchestrator import Orchestrator
from core.retrieval import default_retriever
from mcp.client import LocalRetriever


def main() -> int:
    if len(sys.argv) < 2:
        print("usage: python -m scripts.run_query '<Bahasa query>'", file=sys.stderr)
        return 2

    api_key = os.getenv("ANTHROPIC_API_KEY")
    if not api_key:
        print("error: ANTHROPIC_API_KEY not set. Copy .env.example to .env.", file=sys.stderr)
        return 2

    user_query = sys.argv[1]

    retriever = LocalRetriever(retriever=default_retriever())
    orchestrator = Orchestrator(
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

    state = asyncio.run(orchestrator.run(user_query))
    print(
        json.dumps(
            {
                "query_id": state.query_id,
                "refusal_reason": state.refusal_reason.value if state.refusal_reason else None,
                "answer": state.final_response.answer_markdown if state.final_response else None,
                "citations": [c.model_dump() for c in (state.final_response.citations or [])]
                if state.final_response
                else [],
                "trace": [e.model_dump(mode="json") for e in state.trace_events],
            },
            ensure_ascii=False,
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
