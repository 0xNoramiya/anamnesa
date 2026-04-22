"""A/B benchmark: current (Opus xhigh/xhigh) vs fast (Opus high / Sonnet 4.6 high).

Runs one representative grounded query per config against the real
orchestrator in-process. Prints wall-clock, tokens, decision, and
citation count.

Usage:  python /tmp/bench_agentic.py
"""

from __future__ import annotations

import asyncio
import os
import time
from dataclasses import dataclass

from dotenv import load_dotenv

load_dotenv()

# Lazy imports after env is loaded.
from agents.drafter import OpusDrafter
from agents.normalizer import HaikuNormalizer
from agents.verifier import OpusVerifier
from core.budget import BudgetLimits
from core.orchestrator import Orchestrator
from core.retrieval import default_retriever
from mcp.client import LocalRetriever

QUERY = (
    "Bayi baru lahir tidak menangis, apnea, HR <100. "
    "Langkah resusitasi awal dalam 60 detik pertama?"
)


@dataclass
class Config:
    label: str
    drafter_model: str
    drafter_effort: str
    verifier_model: str
    verifier_effort: str


CONFIGS = [
    Config(
        label="fast-v2 (Opus high / Opus high)",
        drafter_model="claude-opus-4-7",
        drafter_effort="high",
        verifier_model="claude-opus-4-7",
        verifier_effort="high",
    ),
    Config(
        label="fast-v3 (Opus high / Opus medium)",
        drafter_model="claude-opus-4-7",
        drafter_effort="high",
        verifier_model="claude-opus-4-7",
        verifier_effort="medium",
    ),
]


async def run_one(cfg: Config) -> dict:
    api_key = os.environ["ANTHROPIC_API_KEY"]
    hybrid = default_retriever()
    retriever = LocalRetriever(retriever=hybrid)
    orch = Orchestrator(
        normalizer=HaikuNormalizer(
            model_id="claude-haiku-4-5-20251001",
            api_key=api_key,
        ),
        retriever=retriever,
        drafter=OpusDrafter(
            model_id=cfg.drafter_model,
            api_key=api_key,
            retriever=retriever,
            effort=cfg.drafter_effort,
        ),
        verifier=OpusVerifier(
            model_id=cfg.verifier_model,
            api_key=api_key,
            retriever=retriever,
            effort=cfg.verifier_effort,
        ),
        limits=BudgetLimits.from_env(),
    )
    t0 = time.perf_counter()
    state = await orch.run(QUERY)
    wall_ms = int((time.perf_counter() - t0) * 1000)

    cost = state.cost
    fr = state.final_response
    return {
        "label": cfg.label,
        "wall_s": round(wall_ms / 1000, 1),
        "refusal": state.refusal_reason.value if state.refusal_reason else None,
        "citations": len(fr.citations) if fr else 0,
        "input_tok": cost.input_tokens,
        "output_tok": cost.output_tokens,
        "thinking_tok": cost.thinking_tokens,
        "answer_preview": (fr.answer_markdown[:220] + "…") if fr and fr.answer_markdown else "",
    }


async def main() -> None:
    print(f"Query: {QUERY}\n")
    rows = []
    for cfg in CONFIGS:
        print(f"--- {cfg.label} ---")
        row = await run_one(cfg)
        print(f"  wall:     {row['wall_s']} s")
        print(f"  refusal:  {row['refusal']}")
        print(f"  cites:    {row['citations']}")
        print(f"  tokens:   in={row['input_tok']} out={row['output_tok']} think={row['thinking_tok']}")
        print(f"  preview:  {row['answer_preview']}\n")
        rows.append(row)

    # Summary delta.
    b, f = rows[0], rows[1]
    delta_s = b["wall_s"] - f["wall_s"]
    pct = 100 * delta_s / b["wall_s"] if b["wall_s"] else 0
    print("=" * 60)
    print(f"Baseline:  {b['wall_s']}s   cites={b['citations']}   refusal={b['refusal']}")
    print(f"Fast:      {f['wall_s']}s   cites={f['citations']}   refusal={f['refusal']}")
    print(f"Saved:     {delta_s:+.1f}s  ({pct:+.0f}%)")


if __name__ == "__main__":
    asyncio.run(main())
