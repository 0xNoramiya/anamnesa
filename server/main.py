"""FastAPI app for Anamnesa.

Exposes:
  POST /api/query          → start a query, returns {query_id, stream_url}
  GET  /api/stream/{id}    → SSE stream of TraceEvent + final FinalResponse
  GET  /api/pdf/{doc_id}   → serve the cached PDF (for inline viewer)
  GET  /api/manifest       → summary of indexed corpus
  GET  /api/health         → {status: ok, chunks_indexed: N}

The SSE design: one orchestrator run per query, events pushed into an
asyncio.Queue as the state.trace_events list grows. The stream handler
drains the queue, encoding each event as an SSE message. When the
orchestrator finishes, a terminal `final_response` message is sent,
then the queue is closed.

Agents (Normalizer + Drafter + Verifier) are constructed once at startup
so the BGE-M3 model load + HF cache only happens once per process.
"""

from __future__ import annotations

import asyncio
import json
import os
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Any

import structlog
from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from pydantic import BaseModel
from sse_starlette.sse import EventSourceResponse
from ulid import ULID

from core.manifest import Manifest
from core.orchestrator import Orchestrator
from core.state import QueryState, TraceEvent

load_dotenv()
log = structlog.get_logger("anamnesa.server")


def _load_manifest_sync(path: Path) -> Manifest:
    """Sync manifest loader — called only from lifespan boot."""
    if not path.exists():
        return Manifest()
    return Manifest.model_validate_json(path.read_text(encoding="utf-8"))


def _cache_path_exists_sync(p: Path) -> bool:
    return p.exists()


# ---------------------------------------------------------------------------
# Lifespan: build the orchestrator + its agents ONCE so BGE-M3 + HF cache
# only load when the server boots, not per request.
# ---------------------------------------------------------------------------


@asynccontextmanager
async def _lifespan(app: FastAPI):
    from agents.drafter import OpusDrafter
    from agents.normalizer import HaikuNormalizer
    from agents.verifier import OpusVerifier
    from core.budget import BudgetLimits
    from core.retrieval import default_retriever
    from mcp.client import LocalRetriever

    api_key = os.getenv("ANTHROPIC_API_KEY")
    if not api_key:
        raise RuntimeError(
            "ANTHROPIC_API_KEY not set. Copy .env.example to .env."
        )

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

    # Lifespan runs once at boot — sync filesystem I/O here is fine.
    manifest = _load_manifest_sync(Path("catalog/manifest.json"))

    app.state.orchestrator = orchestrator
    app.state.manifest = manifest
    app.state.running_queries = {}  # query_id -> asyncio.Queue
    app.state.tasks = set()           # strong refs to in-flight background tasks
    log.info("anamnesa.boot", docs=len(manifest.documents))
    yield


app = FastAPI(title="Anamnesa", version="0.1.0", lifespan=_lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        os.getenv("ANAMNESA_PUBLIC_ORIGIN", "http://localhost:3000"),
        "http://localhost:3000",
        "http://127.0.0.1:3000",
    ],
    allow_methods=["GET", "POST", "OPTIONS"],
    allow_headers=["*"],
)


# ---------------------------------------------------------------------------
# Schemas
# ---------------------------------------------------------------------------


class QueryRequest(BaseModel):
    query: str


class QueryCreated(BaseModel):
    query_id: str
    stream_url: str


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------


@app.get("/api/health")
async def health() -> dict[str, Any]:
    manifest: Manifest = app.state.manifest
    return {
        "status": "ok",
        "docs_indexed": len(manifest.documents),
        "embedder": os.getenv("ANAMNESA_EMBEDDER", "hash"),
    }


@app.get("/api/manifest")
async def manifest_summary() -> dict[str, Any]:
    m: Manifest = app.state.manifest
    by_status: dict[str, int] = {}
    by_source: dict[str, int] = {}
    for d in m.documents:
        by_status[d.status] = by_status.get(d.status, 0) + 1
        by_source[d.source_type] = by_source.get(d.source_type, 0) + 1
    return {
        "schema_version": m.schema_version,
        "total": len(m.documents),
        "by_status": by_status,
        "by_source_type": by_source,
    }


@app.post("/api/query", response_model=QueryCreated)
async def create_query(req: QueryRequest) -> QueryCreated:
    text = req.query.strip()
    if not text:
        raise HTTPException(400, "empty query")
    query_id = str(ULID())
    queue: asyncio.Queue[dict[str, Any] | None] = asyncio.Queue()
    app.state.running_queries[query_id] = queue

    # Kick off the orchestrator in the background; it publishes each
    # trace event + the final response through the queue. Task reference
    # stashed on app.state so it isn't GC'd before completion.
    task = asyncio.create_task(_run_query(query_id, text, queue))
    app.state.tasks.add(task)
    task.add_done_callback(app.state.tasks.discard)

    return QueryCreated(query_id=query_id, stream_url=f"/api/stream/{query_id}")


async def _run_query(
    query_id: str,
    text: str,
    queue: asyncio.Queue[dict[str, Any] | None],
) -> None:
    orchestrator: Orchestrator = app.state.orchestrator

    # Tee: watch state.trace_events as the orchestrator mutates it, forward
    # new entries to the queue. We run the orchestrator and a pump in
    # parallel via a shared state pointer.
    state_box: dict[str, QueryState] = {}

    async def pump_events() -> None:
        sent = 0
        while True:
            state = state_box.get("state")
            if state is not None:
                events = state.trace_events
                while sent < len(events):
                    ev = events[sent]
                    await queue.put(_trace_to_json(ev))
                    sent += 1
                if state.final_response is not None:
                    await queue.put({
                        "kind": "final",
                        "payload": state.final_response.model_dump(mode="json"),
                    })
                    await queue.put(None)  # sentinel: end of stream
                    return
            await asyncio.sleep(0.05)

    async def run_orch() -> None:
        # Pre-build state so the pump can watch trace_events from turn 0.
        # Orchestrator.run() accepts an optional `state` param precisely
        # for this SSE streaming use case.
        state = QueryState(original_query=text, query_id=query_id)
        state_box["state"] = state
        try:
            await orchestrator.run(text, state=state)
        except Exception as exc:
            # Catch-all by design: anything from model transport, retrieval
            # backend, validation, etc. should become a stream error event
            # rather than crash the request handler. Logged with traceback.
            log.exception("anamnesa.query_failed", query_id=query_id)
            await queue.put(
                {"kind": "error", "payload": {"error": f"{type(exc).__name__}: {exc}"}}
            )
            await queue.put(None)

    try:
        await asyncio.gather(run_orch(), pump_events())
    finally:
        app.state.running_queries.pop(query_id, None)


def _trace_to_json(ev: TraceEvent) -> dict[str, Any]:
    return {"kind": "trace", "payload": ev.model_dump(mode="json")}


@app.get("/api/stream/{query_id}")
async def stream(query_id: str) -> EventSourceResponse:
    queue = app.state.running_queries.get(query_id)
    if queue is None:
        raise HTTPException(404, f"no running query {query_id!r}")

    async def events():
        while True:
            item = await queue.get()
            if item is None:
                yield {"event": "done", "data": ""}
                return
            yield {
                "event": item["kind"],
                "data": json.dumps(item["payload"], ensure_ascii=False),
            }

    return EventSourceResponse(events())


# ---------------------------------------------------------------------------
# PDF passthrough
# ---------------------------------------------------------------------------


@app.get("/api/pdf/{doc_id}")
async def pdf(doc_id: str) -> FileResponse:
    m: Manifest = app.state.manifest
    rec = next((d for d in m.documents if d.doc_id == doc_id), None)
    if rec is None or not rec.cache_path:
        raise HTTPException(404, f"no PDF on record for {doc_id!r}")
    p = Path(rec.cache_path)
    # Sync stat is cheap; ruff ASYNC240 is over-cautious for a one-shot check.
    if not _cache_path_exists_sync(p):
        raise HTTPException(404, f"PDF file missing at {p}")
    return FileResponse(path=p, media_type="application/pdf", filename=p.name)
