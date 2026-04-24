"""Probe: does Opus 4.7 stream token-by-token when thinking_budget=0?

With adaptive thinking on, Opus is silent for ~70s then bursts the whole
tool_use input at once (we measured this earlier). If we disable
thinking, does Opus stream content_block_delta text events like a
normal chat call?

If YES → we can ship Drafter streaming to the SSE channel, user sees
        answer being typed from ~5-10s onward.
If NO  → streaming is still a no-op and we need a different fix.
"""

from __future__ import annotations

import os
import sys
import time

from dotenv import load_dotenv

load_dotenv()

from anthropic import Anthropic

from agents.drafter import _build_initial_user_message, _load_system_prompt, _tool_specs
from core.retrieval import default_retriever
from core.state import NormalizedQuery, QueryState
from mcp.client import LocalRetriever


def extract_content_so_far(accum: str) -> str:
    marker = '"content"'
    pos = accum.find(marker)
    if pos == -1:
        return ""
    i = pos + len(marker)
    while i < len(accum) and accum[i] in " \t\n:":
        i += 1
    if i >= len(accum) or accum[i] != '"':
        return ""
    i += 1
    out: list[str] = []
    while i < len(accum):
        ch = accum[i]
        if ch == "\\":
            if i + 1 >= len(accum):
                break
            esc = accum[i + 1]
            escs = {"n": "\n", "t": "\t", '"': '"', "\\": "\\", "/": "/"}
            if esc in escs:
                out.append(escs[esc])
                i += 2
            elif esc == "u":
                if i + 5 >= len(accum):
                    break
                try:
                    out.append(chr(int(accum[i + 2 : i + 6], 16)))
                    i += 6
                except ValueError:
                    break
            else:
                out.append(esc)
                i += 2
        elif ch == '"':
            break
        else:
            out.append(ch)
            i += 1
    return "".join(out)


async def main():
    nq = NormalizedQuery(
        structured_query="Langkah resusitasi awal neonatus 60 detik pertama",
        intent="tatalaksana",
        patient_context="pediatric",
        condition_tags=["asfiksia_neonatorum"],
        keywords_id=["resusitasi", "neonatus"],
        keywords_en=["neonatal", "resuscitation"],
    )
    state = QueryState(original_query="Resusitasi neonatus?")
    state.normalized_query = nq

    hybrid = default_retriever()
    retriever = LocalRetriever(retriever=hybrid)
    from core.state import RetrievalFilters

    attempt = await retriever.search(nq, RetrievalFilters(), attempt_num=1)
    state.append_retrieval(attempt)

    client = Anthropic(api_key=os.environ["ANTHROPIC_API_KEY"])
    system_prompt = _load_system_prompt()
    user_prompt = _build_initial_user_message(
        nq=nq, chunks=list(attempt.chunks), verifier_feedback=None
    )

    tool_accum: dict[int, str] = {}
    last_emitted: dict[int, int] = {}
    t0 = time.perf_counter()
    first_char_at: float | None = None
    deltas: list[tuple[float, int]] = []

    print(f"retrieval: {len(attempt.chunks)} chunks. starting stream (no thinking)...\n")

    with client.messages.stream(
        model="claude-opus-4-7",
        max_tokens=8000,
        system=[{"type": "text", "text": system_prompt, "cache_control": {"type": "ephemeral"}}],
        tools=_tool_specs(),
        # NO thinking config — thinking_budget=0 equivalent
        messages=[{"role": "user", "content": user_prompt}],
    ) as stream:
        for event in stream:
            t = getattr(event, "type", None)
            if t == "content_block_start":
                block = getattr(event, "content_block", None)
                btype = getattr(block, "type", None)
                idx = getattr(event, "index", 0)
                if btype == "tool_use":
                    tool_accum[idx] = ""
                    last_emitted[idx] = 0
            elif t == "content_block_delta":
                delta = getattr(event, "delta", None)
                dtype = getattr(delta, "type", None)
                idx = getattr(event, "index", 0)
                if dtype == "input_json_delta":
                    frag = getattr(delta, "partial_json", "")
                    tool_accum[idx] = tool_accum.get(idx, "") + frag
                    current = extract_content_so_far(tool_accum[idx])
                    already = last_emitted.get(idx, 0)
                    if len(current) > already:
                        now = time.perf_counter() - t0
                        if first_char_at is None:
                            first_char_at = now
                        new = current[already:]
                        sys.stdout.write(new)
                        sys.stdout.flush()
                        last_emitted[idx] = len(current)
                        deltas.append((now, len(current)))

        final = stream.get_final_message()
        total = time.perf_counter() - t0
        print("\n\n--- done ---")
        print(f"total wall:      {total:.1f}s")
        if first_char_at:
            print(f"first content:   {first_char_at:.1f}s")
        if deltas:
            span = deltas[-1][0] - deltas[0][0]
            chars = deltas[-1][1]
            rate = chars / span if span > 0 else 0
            print(f"content span:    {span:.1f}s ({chars} chars @ {rate:.0f} cps)")
        print(f"stop_reason:     {final.stop_reason}")
        print(f"tokens:          in={final.usage.input_tokens} out={final.usage.output_tokens}")


if __name__ == "__main__":
    os.environ.setdefault("ANAMNESA_EMBEDDER", "bge")
    import asyncio

    asyncio.run(main())
