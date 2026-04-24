"""Clients for Anamnesa's retrieval layer.

Two flavors:

- `LocalRetriever` — in-process adapter that implements the `Retriever`
  Protocol from `agents/base.py` by calling `core/retrieval.py` directly.
  This is what orchestrator wires in when both agents and the retrieval
  layer run in the same process (the hackathon default).

- `RemoteMCPClient` — sketch of a client that speaks to a running
  `anamnesa-mcp` MCP server over stdio/SSE. The official MCP SDK session
  API is young and has some non-obvious setup cost; this class exists so
  the surface is right, with the transport deliberately deferred until it
  matters (post-hackathon, e.g. web frontend talking to a remote server).
"""

from __future__ import annotations

import time
from typing import Any

import structlog

from core.retrieval import HybridRetriever
from core.state import (
    NormalizedQuery,
    RetrievalAttempt,
    RetrievalFilters,
)

log = structlog.get_logger("anamnesa.retrieval")


class LocalRetriever:
    """In-process `Retriever` backed by a `HybridRetriever`.

    Implements `agents.base.Retriever`. Use this from the orchestrator when
    agents and retrieval run in the same process.
    """

    def __init__(self, *, retriever: HybridRetriever) -> None:
        self._r = retriever

    async def search(
        self,
        query: NormalizedQuery,
        filters: RetrievalFilters,
        *,
        attempt_num: int,
    ) -> RetrievalAttempt:
        t0 = time.monotonic()
        chunks = self._r.search_guidelines(query, filters)
        latency_ms = int((time.monotonic() - t0) * 1000)
        return RetrievalAttempt(
            attempt_num=attempt_num,
            filters=filters,
            chunks=chunks,
            latency_ms=latency_ms,
        )

    # Passthroughs with MCP-tool names so agents share one surface regardless
    # of transport.

    def get_full_section(self, doc_id: str, section_path: str) -> dict[str, Any]:
        return self._r.get_full_section(doc_id, section_path)

    def get_pdf_page_url(self, doc_id: str, page: int) -> str:
        return self._r.get_pdf_page_url(doc_id, page)

    def check_supersession(self, doc_id: str) -> dict[str, Any]:
        return self._r.check_supersession(doc_id)


class RemoteMCPClient:
    """Sketch of a remote MCP client for `anamnesa-mcp`.

    Transport intentionally unimplemented. The method surface mirrors
    `LocalRetriever` so call sites can swap one for the other.

    When you wire this, the shape is:

        from mcp.client.stdio import stdio_client
        from mcp.client.session import ClientSession
        async with stdio_client(StdioServerParameters(command="python",
            args=["-m", "mcp.anamnesa_mcp"])) as (r, w):
            async with ClientSession(r, w) as session:
                await session.initialize()
                result = await session.call_tool(
                    "search_guidelines",
                    {"query": ..., "filters": ...},
                )

    Implementing that is straightforward but adds a non-trivial async
    context to every call site; deferring until a real frontend needs it.
    """

    def __init__(self, *, endpoint: str) -> None:
        self.endpoint = endpoint

    async def search(
        self,
        query: NormalizedQuery,
        filters: RetrievalFilters,
        *,
        attempt_num: int,
    ) -> RetrievalAttempt:
        raise NotImplementedError(
            "RemoteMCPClient.search: wire MCP SDK ClientSession. "
            "Use LocalRetriever for in-process calls in the meantime."
        )

    async def get_full_section(self, doc_id: str, section_path: str) -> dict[str, Any]:
        raise NotImplementedError("RemoteMCPClient.get_full_section: pending transport")

    async def get_pdf_page_url(self, doc_id: str, page: int) -> str:
        raise NotImplementedError("RemoteMCPClient.get_pdf_page_url: pending transport")

    async def check_supersession(self, doc_id: str) -> dict[str, Any]:
        raise NotImplementedError("RemoteMCPClient.check_supersession: pending transport")


__all__ = ["LocalRetriever", "RemoteMCPClient"]
