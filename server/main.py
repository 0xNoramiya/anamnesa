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
from core.retrieval import HybridRetriever
from core.state import NormalizedQuery, QueryState, RetrievalFilters, TraceEvent

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
    from core.cache import DEFAULT_TTL_SECONDS, AnswerCache
    from core.feedback import FeedbackStore
    from core.retrieval import default_retriever
    from mcp.client import LocalRetriever

    api_key = os.getenv("ANTHROPIC_API_KEY")
    if not api_key:
        raise RuntimeError(
            "ANTHROPIC_API_KEY not set. Copy .env.example to .env."
        )

    hybrid = default_retriever()
    retriever = LocalRetriever(retriever=hybrid)

    cache: AnswerCache | None = None
    if os.getenv("ANAMNESA_CACHE_DISABLED", "").lower() not in ("1", "true", "yes"):
        cache_path = Path(
            os.getenv("ANAMNESA_CACHE_PATH", "catalog/cache/answers.db")
        )
        cache_ttl = int(os.getenv("ANAMNESA_CACHE_TTL_S", DEFAULT_TTL_SECONDS))
        cache = AnswerCache(cache_path, ttl_seconds=cache_ttl)

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
            effort=os.getenv("ANAMNESA_DRAFTER_EFFORT", "xhigh"),
        ),
        verifier=OpusVerifier(
            model_id=os.getenv("ANAMNESA_MODEL_VERIFIER", "claude-opus-4-7"),
            api_key=api_key,
            retriever=retriever,
            thinking_budget=int(os.getenv("ANAMNESA_VERIFIER_THINKING_BUDGET", 12000)),
            effort=os.getenv("ANAMNESA_VERIFIER_EFFORT", "xhigh"),
        ),
        limits=BudgetLimits.from_env(),
        cache=cache,
    )

    # Lifespan runs once at boot — sync filesystem I/O here is fine.
    manifest = _load_manifest_sync(Path("catalog/manifest.json"))

    feedback_path = Path(os.getenv("ANAMNESA_FEEDBACK_PATH", "catalog/cache/feedback.db"))
    feedback = FeedbackStore(feedback_path)

    app.state.orchestrator = orchestrator
    app.state.hybrid = hybrid         # exposed for /api/search (fast mode)
    app.state.manifest = manifest
    app.state.cache = cache           # exposed for /api/cache/* admin endpoints
    app.state.feedback = feedback     # thumbs up/down store
    app.state.running_queries = {}    # query_id -> asyncio.Queue
    app.state.tasks = set()           # strong refs to in-flight background tasks
    app.state.version = _detect_version()  # git sha + date; stable at boot
    log.info(
        "anamnesa.boot",
        docs=len(manifest.documents),
        cache_enabled=cache is not None,
        version_sha=app.state.version.get("sha", "dev"),
    )
    yield
    if cache is not None:
        cache.close()
    feedback.close()


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


class FeedbackRequest(BaseModel):
    query_id: str
    query_text: str
    rating: str                    # "up" | "down"
    note: str | None = None
    answer_sha: str | None = None


class FeedbackResponse(BaseModel):
    id: str
    stored: bool = True


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


@app.get("/api/meta")
async def meta() -> dict[str, Any]:
    """Compact build + corpus + cache summary — fetched by the web footer
    so every page shows what it's actually running against. Cached at
    boot for version; cache stats are live."""
    manifest: Manifest = app.state.manifest
    hybrid = app.state.hybrid
    cache: AnswerCache | None = getattr(app.state, "cache", None)

    # Corpus year range — loop is cheap, 80 entries.
    years = [d.year for d in manifest.documents if d.year]
    year_min = min(years) if years else None
    year_max = max(years) if years else None

    # Chunk count — prefer the BM25-backed store since it's authoritative
    # for what's actually queryable.
    try:
        chunk_count = int(len(getattr(hybrid, "_bm25_chunks", []) or []))
    except Exception:
        chunk_count = 0

    cache_stats = cache.stats() if cache is not None else None

    return {
        "version": app.state.version,
        "corpus": {
            "docs": len(manifest.documents),
            "chunks": chunk_count,
            "year_min": year_min,
            "year_max": year_max,
            "embedder": os.getenv("ANAMNESA_EMBEDDER", "hash"),
        },
        "cache": cache_stats,
        "legal_basis": "UU No. 28/2014 Pasal 42",
    }


def _detect_version() -> dict[str, str]:
    """Read the git HEAD sha + date at boot. Falls back to 'dev' on any
    failure (non-git checkout, no git binary, detached HEAD, etc.)."""
    import subprocess

    def _run(cmd: list[str]) -> str | None:
        try:
            out = subprocess.check_output(
                cmd, cwd=os.path.dirname(__file__) or ".", stderr=subprocess.DEVNULL
            )
            return out.decode("utf-8", errors="replace").strip() or None
        except Exception:
            return None

    sha = _run(["git", "rev-parse", "--short=12", "HEAD"]) or "dev"
    date = _run(["git", "log", "-1", "--format=%cI", "HEAD"]) or ""
    subject = _run(["git", "log", "-1", "--format=%s", "HEAD"]) or ""
    return {
        "sha": sha,
        "date": date,
        "subject": subject[:120],
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


@app.get("/api/search")
async def fast_search(q: str, limit: int = 20) -> dict[str, Any]:
    """Fast-path retrieval: no LLM, no agents.

    Returns the top-N ranked chunks for a query as JSON. Intended for
    pasal.id-style "just show me which PDF says this" browsing. The
    agentic pipeline (POST /api/query) is the opt-in mode for actual
    synthesis with citations + verifier.
    """
    q_clean = q.strip()
    if not q_clean:
        raise HTTPException(400, "empty query")
    # Cap to sane bounds — retriever fans out both BM25 + vector by 3x
    # internally, so limit=20 already means 60 candidates fused.
    limit = max(1, min(int(limit), 50))

    hybrid: HybridRetriever = app.state.hybrid
    nq = NormalizedQuery(
        structured_query=q_clean,
        keywords_id=[t for t in q_clean.split() if len(t) >= 2],
    )
    chunks = hybrid.search_guidelines(nq, RetrievalFilters(top_k=limit))

    # Also surface doc-level aggregates so the UI can show "3 PDFs, 12 hits".
    per_doc: dict[str, int] = {}
    for c in chunks:
        per_doc[c.doc_id] = per_doc.get(c.doc_id, 0) + 1

    return {
        "query": q_clean,
        "count": len(chunks),
        "docs": [
            {"doc_id": d, "hits": n}
            for d, n in sorted(per_doc.items(), key=lambda kv: -kv[1])
        ],
        "results": [c.model_dump(mode="json") for c in chunks],
    }


@app.post("/api/feedback", response_model=FeedbackResponse)
async def post_feedback(req: FeedbackRequest) -> FeedbackResponse:
    if req.rating not in ("up", "down"):
        raise HTTPException(400, "rating must be 'up' or 'down'")
    if not req.query_id.strip() or not req.query_text.strip():
        raise HTTPException(400, "query_id and query_text are required")
    store = getattr(app.state, "feedback", None)
    if store is None:
        raise HTTPException(503, "feedback store not initialized")
    try:
        entry_id = store.add(
            query_id=req.query_id.strip(),
            query_text=req.query_text.strip(),
            rating=req.rating,
            note=req.note,
            answer_sha=req.answer_sha,
        )
    except ValueError as exc:
        raise HTTPException(400, str(exc))
    return FeedbackResponse(id=entry_id, stored=True)


@app.get("/api/feedback/stats")
async def feedback_stats() -> dict[str, Any]:
    store = getattr(app.state, "feedback", None)
    if store is None:
        raise HTTPException(503, "feedback store not initialized")
    return store.stats()


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

    # Intentionally NOT popping running_queries here — see the stream
    # handler. Fast-finishing queries (e.g. normalizer refusals) can
    # complete before the client connects to the stream; keeping the
    # queue alive until the stream is drained avoids a race 404.
    await asyncio.gather(run_orch(), pump_events())


def _trace_to_json(ev: TraceEvent) -> dict[str, Any]:
    return {"kind": "trace", "payload": ev.model_dump(mode="json")}


@app.get("/api/stream/{query_id}")
async def stream(query_id: str) -> EventSourceResponse:
    queue = app.state.running_queries.get(query_id)
    if queue is None:
        raise HTTPException(404, f"no running query {query_id!r}")

    async def events():
        try:
            while True:
                item = await queue.get()
                if item is None:
                    yield {"event": "done", "data": ""}
                    return
                yield {
                    "event": item["kind"],
                    "data": json.dumps(item["payload"], ensure_ascii=False),
                }
        finally:
            # The stream owns queue cleanup — stream completion (drained
            # or client disconnect) is the correct trigger to pop.
            app.state.running_queries.pop(query_id, None)

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
    # `inline` so the browser's built-in PDF viewer (or our iframe) renders
    # it; omit `filename=` to avoid the default `attachment` disposition.
    return FileResponse(
        path=p,
        media_type="application/pdf",
        content_disposition_type="inline",
    )
