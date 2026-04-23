"""Probe the multi-turn follow-up path end-to-end against a local server.

Fires two queries in sequence:
  1. "DBD derajat II dewasa, kapan dirujuk dari Puskesmas?"
  2. "dan kalau anak?" with prior_query/prior_answer from turn 1

Reports what the Normalizer's `structured_query` + condition_tags +
patient_context look like for each turn — the key signal that the
follow-up was condensed into a standalone query with the right
population context carried over.
"""

from __future__ import annotations

import json
import sys
import time

import httpx

BASE = "http://127.0.0.1:8787"


def run_turn(
    query: str,
    prior_query: str | None = None,
    prior_answer: str | None = None,
) -> tuple[dict, dict]:
    body: dict = {"query": query}
    if prior_query and prior_answer:
        body["prior_query"] = prior_query
        body["prior_answer"] = prior_answer
    r = httpx.post(f"{BASE}/api/query", json=body, timeout=30)
    r.raise_for_status()
    created = r.json()
    qid = created["query_id"]
    print(f"  → POST /api/query qid={qid}")

    final = None
    normalized = None
    current_event: str | None = None
    t0 = time.monotonic()
    with httpx.stream("GET", f"{BASE}/api/stream/{qid}", timeout=300) as resp:
        for raw in resp.iter_lines():
            raw = raw.strip()
            if not raw:
                current_event = None
                continue
            if raw.startswith("event:"):
                current_event = raw[6:].strip()
                continue
            if not raw.startswith("data:"):
                continue
            data = raw[5:].strip()
            if not data:
                continue
            try:
                payload = json.loads(data)
            except json.JSONDecodeError:
                continue
            if current_event == "trace":
                if (
                    payload.get("agent") == "normalizer"
                    and payload.get("event_type") == "normalized"
                ):
                    normalized = payload
            elif current_event == "final":
                final = payload
                break
    dur = time.monotonic() - t0
    print(f"  ← final in {dur:.1f}s")
    return normalized or {}, final or {}


def main() -> int:
    print("=== turn 1: initial DBD query ===")
    q1 = "DBD derajat II dewasa, kapan dirujuk dari Puskesmas?"
    print(f"  query: {q1}")
    norm1, final1 = run_turn(q1)
    if not final1:
        print("  FAIL: no final response")
        return 1
    tags1 = (norm1.get("payload") or {}).get("condition_tags")
    pop1 = (norm1.get("payload") or {}).get("patient_context")
    print(f"  normalized.condition_tags: {tags1}")
    print(f"  normalized.patient_context: {pop1}")
    print(f"  refusal: {final1.get('refusal_reason')}")
    print(f"  citations: {len(final1.get('citations') or [])}")
    md = final1.get("answer_markdown") or ""
    print(f"  md len: {len(md)}")
    print(f"  md head: {md[:240]!r}")
    print()

    print("=== turn 2: follow-up 'dan kalau anak?' ===")
    q2 = "dan kalau anak?"
    prior_q = q1
    prior_a = md
    print(f"  query: {q2}")
    print(f"  (prior_query shipped, prior_answer={len(prior_a)} chars)")
    norm2, final2 = run_turn(q2, prior_q, prior_a)
    if not final2:
        print("  FAIL: no final response on turn 2")
        return 1
    tags2 = (norm2.get("payload") or {}).get("condition_tags")
    pop2 = (norm2.get("payload") or {}).get("patient_context")
    print(f"  normalized.condition_tags: {tags2}")
    print(f"  normalized.patient_context: {pop2}")
    print(f"  refusal: {final2.get('refusal_reason')}")
    print(f"  citations: {len(final2.get('citations') or [])}")
    md2 = final2.get("answer_markdown") or ""
    print(f"  md len: {len(md2)}")
    print(f"  md head: {md2[:300]!r}")

    # Acceptance signals: turn 2 should (a) not refuse, (b) reflect
    # pediatric population in its normalized metadata or prose.
    if final2.get("refusal_reason"):
        print("\nFAIL: turn 2 refused — follow-up context didn't land.")
        return 1

    # Pediatric signal check — look for "anak" / "pediatri" / "pedia-"
    # in condition_tags, patient_context, or the first 400 chars of the
    # answer. Loose: any hit is a pass.
    blob = " ".join(
        [
            " ".join(tags2 or []),
            str(pop2 or ""),
            md2[:400],
        ]
    ).lower()
    peds_hit = any(kw in blob for kw in ["anak", "pediatri", "pedia"])
    if peds_hit:
        print("\nPASS: pediatric context carried into turn 2.")
        return 0
    print("\nWARN: turn 2 didn't surface a pediatric hint in the expected places.")
    print("      (might still be valid if the answer addresses children without the keyword)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
