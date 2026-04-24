"""Probe: if Drafter prompt asks for prose FIRST + tool-call second,
do we get text_delta streams?

This verifies the premise of the streaming refactor before committing.
"""

from __future__ import annotations

import asyncio
import os
import sys
import time

from dotenv import load_dotenv

load_dotenv()

from anthropic import Anthropic


async def main() -> None:
    client = Anthropic(api_key=os.environ["ANTHROPIC_API_KEY"])

    system = (
        "You are a Bahasa medical-citation assistant.\n\n"
        "FORMAT: First, write your answer as natural Bahasa prose of 3-4 "
        "sentences with inline [[ppk-fktp-2023:p142:dbd]] citation "
        "markers. Then call `submit_citations` with a list of the "
        "citation keys you used. The tool call MUST come AFTER the "
        "prose — do not emit the tool call first."
    )
    user = (
        "Kapan harus rujuk pasien DBD derajat II dewasa dari Puskesmas? "
        "Gunakan 2-3 kutipan dari PPK FKTP 2023."
    )

    t0 = time.perf_counter()
    text_buf = ""
    tool_buf = ""
    first_text_at: float | None = None

    with client.messages.stream(
        model="claude-opus-4-7",
        max_tokens=1500,
        system=system,
        tools=[
            {
                "name": "submit_citations",
                "description": "Submit citation keys used in the prose.",
                "input_schema": {
                    "type": "object",
                    "properties": {
                        "citations": {
                            "type": "array",
                            "items": {"type": "string"},
                        },
                    },
                    "required": ["citations"],
                },
            }
        ],
        messages=[{"role": "user", "content": user}],
    ) as stream:
        for event in stream:
            t = getattr(event, "type", None)
            if t == "content_block_delta":
                delta = getattr(event, "delta", None)
                dtype = getattr(delta, "type", None)
                if dtype == "text_delta":
                    frag = getattr(delta, "text", "")
                    if first_text_at is None:
                        first_text_at = time.perf_counter() - t0
                    text_buf += frag
                    sys.stdout.write(frag)
                    sys.stdout.flush()
                elif dtype == "input_json_delta":
                    frag = getattr(delta, "partial_json", "")
                    tool_buf += frag

        final = stream.get_final_message()
        total = time.perf_counter() - t0
        print("\n\n--- done ---")
        print(f"total wall:        {total:.1f}s")
        print(f"first text delta:  {first_text_at:.1f}s" if first_text_at else "no text")
        print(f"text chars:        {len(text_buf)}")
        print(f"tool input:        {tool_buf!r}")
        print(f"stop_reason:       {final.stop_reason}")


if __name__ == "__main__":
    asyncio.run(main())
