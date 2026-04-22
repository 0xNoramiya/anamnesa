"""`anamnesa-mcp` — the single retrieval boundary for Drafter/Verifier.

Tools exposed (exactly per CLAUDE.md > Agent roster):

  - search_guidelines(query, filters) -> list[Chunk]
  - get_full_section(doc_id, section_path) -> {doc_id, section_path, text}
  - get_pdf_page_url(doc_id, page) -> str
  - check_supersession(doc_id) -> {status, superseding_doc_id|null, source_year}

The server delegates to `core/retrieval.py`. For in-process use (orchestrator,
tests) prefer `mcp.client.LocalRetriever`, which calls the same primitives
without a JSON-RPC round trip.

Note on the package name collision: this repo owns a local `mcp/` package
which shadows the installed MCP SDK of the same name. We import the SDK via
`_load_mcp_sdk()` below, which temporarily swaps `sys.modules["mcp"]`. The
alternative — renaming our package — would require edits outside this PR's
scope.
"""

from __future__ import annotations

import importlib
import importlib.util
import os
import sys
from pathlib import Path
from types import ModuleType
from typing import Any

import structlog

from core.retrieval import HybridRetriever, default_retriever
from core.state import Chunk, NormalizedQuery, RetrievalFilters

log = structlog.get_logger("anamnesa.mcp")

# ---------------------------------------------------------------------------
# Load the installed MCP SDK despite our local `mcp/` package shadowing it.
# ---------------------------------------------------------------------------


def _load_mcp_sdk() -> ModuleType:
    """Return the installed `mcp` SDK as a module (not our local package).

    Strategy: find the `mcp` distribution's __init__.py inside site-packages,
    load it under the same import name, and also prime the submodules we
    need (`mcp.server.fastmcp`, `mcp.server.stdio`). Callers can then do
    `sdk.server.fastmcp.FastMCP` without the shadow getting in the way.
    """
    # Find the real mcp package path. It's the one that sits in a
    # `site-packages/mcp/__init__.py` — any path containing the sentinel
    # subdir `server/fastmcp`.
    candidate: Path | None = None
    for p in sys.path:
        probe = Path(p) / "mcp" / "server" / "fastmcp" / "__init__.py"
        if probe.is_file():
            candidate = Path(p) / "mcp"
            break
    if candidate is None:
        raise ImportError(
            "Installed `mcp` SDK not found on sys.path. "
            "`pip install mcp` (already in pyproject.toml deps)."
        )

    # Preserve the local shadow so other code (importing `mcp.anamnesa_mcp`)
    # still works after we restore it.
    local_mcp = sys.modules.get("mcp")

    # Build fresh spec pointed at the real init and a search path.
    init_file = candidate / "__init__.py"
    spec = importlib.util.spec_from_file_location(
        "mcp",
        init_file,
        submodule_search_locations=[str(candidate)],
    )
    if spec is None or spec.loader is None:
        raise ImportError("failed to build spec for mcp SDK")

    sdk = importlib.util.module_from_spec(spec)
    sys.modules["mcp"] = sdk
    try:
        spec.loader.exec_module(sdk)
        # Prime the submodules we care about while the SDK owns the name.
        importlib.import_module("mcp.server")
        importlib.import_module("mcp.server.fastmcp")
        importlib.import_module("mcp.server.stdio")
    finally:
        # Restore our local package so other repo modules keep working.
        if local_mcp is not None:
            sys.modules["mcp"] = local_mcp
        else:
            sys.modules.pop("mcp", None)
    return sdk


# ---------------------------------------------------------------------------
# Tool schemas — kept as thin wrappers so the SDK handles validation.
# Each tool name MUST match the names referenced by agents/prompts/*.md.
# ---------------------------------------------------------------------------


def _chunk_to_dict(c: Chunk) -> dict[str, Any]:
    return {
        "doc_id": c.doc_id,
        "page": c.page,
        "section_slug": c.section_slug,
        "section_path": c.section_path,
        "text": c.text,
        "year": c.year,
        "source_type": c.source_type,
        "score": c.score,
        "retrieval_method": c.retrieval_method,
        "source_url": c.source_url,
    }


def _filters_from_dict(data: dict[str, Any] | None) -> RetrievalFilters:
    if not data:
        return RetrievalFilters()
    return RetrievalFilters.model_validate(data)


def _query_from_payload(payload: str | dict[str, Any]) -> NormalizedQuery:
    """Accept either a raw string or a NormalizedQuery dict."""
    if isinstance(payload, str):
        return NormalizedQuery(structured_query=payload)
    return NormalizedQuery.model_validate(payload)


def build_tool_handlers(
    retriever: HybridRetriever,
) -> dict[str, Any]:
    """Return a dict of `name -> async callable` implementing the four tools.

    Exposed as a standalone helper so tests and the Local client can exercise
    the same code path the MCP server uses, without going through JSON-RPC.
    """

    async def search_guidelines(
        query: str | dict[str, Any],
        filters: dict[str, Any] | None = None,
    ) -> list[dict[str, Any]]:
        normalized = _query_from_payload(query)
        chunks = retriever.search_guidelines(normalized, _filters_from_dict(filters))
        return [_chunk_to_dict(c) for c in chunks]

    async def get_full_section(doc_id: str, section_path: str) -> dict[str, Any]:
        return retriever.get_full_section(doc_id, section_path)

    async def get_pdf_page_url(doc_id: str, page: int) -> str:
        return retriever.get_pdf_page_url(doc_id, int(page))

    async def check_supersession(doc_id: str) -> dict[str, Any]:
        return retriever.check_supersession(doc_id)

    return {
        "search_guidelines": search_guidelines,
        "get_full_section": get_full_section,
        "get_pdf_page_url": get_pdf_page_url,
        "check_supersession": check_supersession,
    }


# ---------------------------------------------------------------------------
# MCP server entry point
# ---------------------------------------------------------------------------


def build_server(retriever: HybridRetriever | None = None) -> Any:
    """Construct an `mcp.server.fastmcp.FastMCP` with our four tools bound.

    Returns the SDK server instance. Kept separate from `serve()` so tests
    and alternate runners can construct it without taking over stdin/out.
    """
    r = retriever or default_retriever()
    sdk = _load_mcp_sdk()
    fast_mcp_cls = sdk.server.fastmcp.FastMCP

    server = fast_mcp_cls(name="anamnesa-mcp", instructions=(
        "Retrieval layer for Indonesian clinical guidelines. "
        "All tools are grounded in the Anamnesa corpus; responses are "
        "Bahasa Indonesia text chunks with structured metadata."
    ))

    handlers = build_tool_handlers(r)

    @server.tool(
        name="search_guidelines",
        description=(
            "Hybrid (vector + BM25) search over the Indonesian clinical "
            "guideline corpus. Returns ranked Chunk dicts."
        ),
    )
    async def _search_guidelines(  # type: ignore[no-redef]
        query: str,
        filters: dict[str, Any] | None = None,
    ) -> list[dict[str, Any]]:
        return await handlers["search_guidelines"](query, filters)

    @server.tool(
        name="get_full_section",
        description=(
            "Fetch the full section text for a (doc_id, section_path). "
            "Does NOT count against the retrieval budget."
        ),
    )
    async def _get_full_section(doc_id: str, section_path: str) -> dict[str, Any]:  # type: ignore[no-redef]
        return await handlers["get_full_section"](doc_id, section_path)

    @server.tool(
        name="get_pdf_page_url",
        description=(
            "Return a URL pointing at a specific page of the cached PDF "
            "for a doc_id. Uses ANAMNESA_PUBLIC_ORIGIN when set, else "
            "file:// locally."
        ),
    )
    async def _get_pdf_page_url(doc_id: str, page: int) -> str:  # type: ignore[no-redef]
        return await handlers["get_pdf_page_url"](doc_id, page)

    @server.tool(
        name="check_supersession",
        description=(
            "Return supersession/currency info for a doc_id: "
            "{status, superseding_doc_id, source_year}. "
            "status is one of current|superseded|aging|unknown."
        ),
    )
    async def _check_supersession(doc_id: str) -> dict[str, Any]:  # type: ignore[no-redef]
        return await handlers["check_supersession"](doc_id)

    return server


def serve() -> None:
    """Run the MCP server on stdio. Entry point for `python -m mcp.anamnesa_mcp`."""

    server = build_server()
    log.info("mcp.server_starting", tools=4, lance=os.environ.get("LANCE_DB_PATH"))
    # FastMCP.run dispatches to the right transport given the default args.
    server.run()


class AnamnesaMCPClient:
    """Legacy HTTP client stub. Kept so `scripts/run_query.py` still imports.

    Prefer `mcp.client.LocalRetriever` for in-process use, or
    `mcp.client.RemoteMCPClient` once the MCP transport is wired.
    """

    def __init__(self, *, base_url: str) -> None:
        self.base_url = base_url

    async def search(self, *args: object, **kwargs: object) -> object:
        raise NotImplementedError(
            "AnamnesaMCPClient is a shim. Use LocalRetriever (in-process) "
            "or RemoteMCPClient (post-transport)."
        )


if __name__ == "__main__":
    serve()
