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
import re
from contextlib import asynccontextmanager
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import structlog
from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, PlainTextResponse, Response
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
            model_id=(verifier_model := os.getenv("ANAMNESA_MODEL_VERIFIER", "claude-opus-4-7")),
            api_key=api_key,
            retriever=retriever,
            # Haiku 4.5 doesn't support adaptive thinking — auto-zero the
            # budget when the env points at Haiku so ops can swap models
            # with a single env change.
            thinking_budget=(
                0 if "haiku" in verifier_model
                else int(os.getenv("ANAMNESA_VERIFIER_THINKING_BUDGET", 12000))
            ),
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
    # Optional prior-turn context for multi-turn chat. When present, the
    # Normalizer sees the last Q/A and can condense a terse follow-up
    # ("dan kalau anak?") into a standalone query before retrieval.
    prior_query: str | None = None
    prior_answer: str | None = None


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
async def manifest_summary(full: int = 0) -> dict[str, Any]:
    """Aggregates (default) + optionally a flat list of documents when
    `?full=1` — consumed by the /guideline library UI."""
    m: Manifest = app.state.manifest
    by_status: dict[str, int] = {}
    by_source: dict[str, int] = {}
    for d in m.documents:
        by_status[d.status] = by_status.get(d.status, 0) + 1
        by_source[d.source_type] = by_source.get(d.source_type, 0) + 1

    payload: dict[str, Any] = {
        "schema_version": m.schema_version,
        "total": len(m.documents),
        "by_status": by_status,
        "by_source_type": by_source,
    }

    if full:
        this_year = datetime.now(UTC).year
        documents: list[dict[str, Any]] = []
        for d in m.documents:
            if d.superseded_by:
                currency = "superseded"
            elif d.status == "failed":
                currency = "unknown"
            elif d.year and d.year <= this_year - 5:
                currency = "aging"
            else:
                currency = "current"
            documents.append(
                {
                    "doc_id": d.doc_id,
                    "title": d.title,
                    "source_type": d.source_type,
                    "year": d.year,
                    "pages": d.pages,
                    "authority": d.authority,
                    "kepmenkes_number": d.kepmenkes_number,
                    "status": d.status,
                    "currency_status": currency,
                    "superseded_by": list(d.superseded_by),
                    "supersedes": list(d.supersedes),
                }
            )
        # Stable sort: newest year first, then title.
        documents.sort(key=lambda r: (-(r["year"] or 0), r["title"].lower()))
        payload["documents"] = documents

    return payload


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


# ---------------------------------------------------------------------------
# Drug lookup — pure text search over the Fornas (BPJS formulary) chunks.
# No LLM, target <300ms. Fornas is page-chunked, so a single hit returns
# the whole page as a snippet and a link to the guideline HTML anchor.
# ---------------------------------------------------------------------------

_DRUG_DOC_ID = "fornas-2023"
_drug_chunks_cache: list[dict[str, Any]] | None = None


def _load_drug_chunks() -> list[dict[str, Any]]:
    global _drug_chunks_cache
    if _drug_chunks_cache is not None:
        return _drug_chunks_cache
    p = Path("catalog/processed/fornas") / f"{_DRUG_DOC_ID}.json"
    if not p.exists():
        _drug_chunks_cache = []
        return _drug_chunks_cache
    try:
        raw = json.loads(p.read_text(encoding="utf-8"))
    except Exception:
        _drug_chunks_cache = []
        return _drug_chunks_cache
    _drug_chunks_cache = raw if isinstance(raw, list) else []
    return _drug_chunks_cache


# Common EN → ID drug-name transliterations. Fornas uses the Indonesian
# orthography ("parasetamol", "amoksisilin"), but doctors often type the
# international spelling. Run the fallback only when the literal query
# produces zero hits. Order matters — longer, more specific rules first.
_DRUG_EN_TO_ID_SUBS: list[tuple[str, str]] = [
    ("cipro", "sipro"),
    ("cephal", "sefal"),
    ("cefa", "sefa"),
    ("cefo", "sefo"),
    ("cefu", "sefu"),
    ("cefi", "sefi"),
    ("cef", "sef"),
    ("ceph", "sef"),
    ("chlor", "klor"),
    ("erythro", "eritro"),
    ("codei", "kodei"),
    ("phen", "fen"),
    ("ph", "f"),
    ("cillin", "silin"),
    ("cycline", "siklin"),
    ("cetamol", "setamol"),
    ("floxacin", "floksasin"),
    ("mycin", "misin"),
    ("icol", "ikol"),
    ("thia", "tia"),
    ("ck", "k"),
    ("x", "ks"),
]


def _transliterate_en_to_id(s: str) -> str:
    out = s.lower()
    for old, new in _DRUG_EN_TO_ID_SUBS:
        out = out.replace(old, new)
    # Trailing "e" is an EN spelling artefact for many drug names
    # (amlodipine, codeine, morphine); Fornas drops it.
    if out.endswith("e") and len(out) > 3:
        out = out[:-1]
    return out


def _drug_snippet(text: str, q_lower: str, window: int = 80) -> str:
    """Extract the short window around the first hit. Keeps output compact
    for list rendering; full page is still viewable via the anchor link."""
    text_lower = text.lower()
    idx = text_lower.find(q_lower)
    if idx < 0:
        return text[: window * 2].strip()
    start = max(0, idx - window)
    end = min(len(text), idx + len(q_lower) + window)
    snippet = text[start:end].strip()
    if start > 0:
        snippet = "…" + snippet
    if end < len(text):
        snippet = snippet + "…"
    return snippet


@app.get("/api/drug-lookup")
async def drug_lookup(q: str, limit: int = 15) -> dict[str, Any]:
    """Pure text search over Fornas (BPJS formulary) page chunks.

    Each Fornas page lists drug entries with their form, dose, and any
    restrictions (peresepan maksimal, indikasi, catatan). Doctors want
    to answer "is drug X covered by BPJS and what restrictions apply"
    in one look — this endpoint returns matching pages with a short
    contextual snippet, ordered by hit count per page.
    """
    q_clean = q.strip()
    if len(q_clean) < 2:
        raise HTTPException(400, "query must be at least 2 characters")
    limit = max(1, min(int(limit), 50))

    q_lower = q_clean.lower()
    chunks = _load_drug_chunks()

    def _search(qlow: str) -> list[dict[str, Any]]:
        hits: list[dict[str, Any]] = []
        for c in chunks:
            text = str(c.get("text", ""))
            n = text.lower().count(qlow)
            if n == 0:
                continue
            page = int(c.get("page", 0) or 0)
            hits.append({
                "page": page,
                "section_slug": c.get("section_slug", f"halaman-{page}"),
                "hits": n,
                "snippet": _drug_snippet(text, qlow),
            })
        return hits

    results = _search(q_lower)
    matched_query = q_clean
    translit_used = False
    if not results:
        translit = _transliterate_en_to_id(q_lower)
        if translit != q_lower:
            translit_results = _search(translit)
            if translit_results:
                results = translit_results
                matched_query = translit
                translit_used = True

    # Rank: most hits first, then page ascending as a stable tiebreaker.
    results.sort(key=lambda r: (-r["hits"], r["page"]))
    total_hits = sum(r["hits"] for r in results)
    total_pages = len(results)
    results = results[:limit]

    return {
        "query": q_clean,
        "matched_query": matched_query,
        "translit_used": translit_used,
        "doc_id": _DRUG_DOC_ID,
        "doc_title": "Formularium Nasional (Kepmenkes 2197/2023)",
        "source_url": "https://farmalkes.kemkes.go.id/en/unduh/kepmenkes-2197-2023/",
        "total_hits": total_hits,
        "total_pages": total_pages,
        "results": results,
    }


@app.get("/api/drug-mentions")
async def drug_mentions(
    q: str,
    exclude: str = _DRUG_DOC_ID,
    limit: int = 12,
) -> dict[str, Any]:
    """Find pages across the WHOLE corpus (minus Fornas by default) where
    a drug name is mentioned. Companion to /api/drug-lookup — Fornas
    tells you whether BPJS covers it, this tells you where PPK/PNPK
    discuss the clinical use of it.

    Pure case-insensitive substring match over the in-memory BM25 chunk
    cache — no tokenization, no LLM, ~5-10 ms on 9k chunks.
    """
    q_clean = q.strip()
    if len(q_clean) < 3:
        raise HTTPException(400, "query must be at least 3 characters")
    limit = max(1, min(int(limit), 50))

    exclude_ids = {s for s in (exclude or "").split(",") if s.strip()}
    hybrid: HybridRetriever = app.state.hybrid
    all_chunks = getattr(hybrid, "_bm25_chunks", []) or []

    q_lower = q_clean.lower()
    translit_used = False

    def _scan(qlow: str) -> list[dict[str, Any]]:
        hits: list[dict[str, Any]] = []
        for c in all_chunks:
            if c.doc_id in exclude_ids:
                continue
            text = c.text or ""
            n = text.lower().count(qlow)
            if n == 0:
                continue
            hits.append({
                "doc_id": c.doc_id,
                "page": int(c.page or 0),
                "section_path": c.section_path,
                "section_slug": c.section_slug,
                "hits": n,
                "snippet": _drug_snippet(text, qlow),
            })
        return hits

    matches = _scan(q_lower)
    matched_query = q_clean
    if not matches:
        translit = _transliterate_en_to_id(q_lower)
        if translit != q_lower:
            alt = _scan(translit)
            if alt:
                matches = alt
                matched_query = translit
                translit_used = True

    # Collapse to one row per (doc_id, page), ranked by hits desc then page asc.
    matches.sort(key=lambda r: (-r["hits"], r["doc_id"], r["page"]))

    # Attach doc titles + year from the manifest for the UI.
    m: Manifest = app.state.manifest
    doc_meta: dict[str, dict[str, Any]] = {
        d.doc_id: {"title": d.title, "year": d.year, "source_type": d.source_type}
        for d in m.documents
    }

    # Per-doc aggregate for the header summary.
    per_doc: dict[str, dict[str, Any]] = {}
    for row in matches:
        did = row["doc_id"]
        if did not in per_doc:
            meta = doc_meta.get(did, {})
            per_doc[did] = {
                "doc_id": did,
                "title": meta.get("title", did),
                "year": meta.get("year"),
                "source_type": meta.get("source_type"),
                "page_count": 0,
                "hit_count": 0,
            }
        per_doc[did]["page_count"] += 1
        per_doc[did]["hit_count"] += row["hits"]

    docs_sorted = sorted(
        per_doc.values(), key=lambda d: (-d["hit_count"], d["doc_id"])
    )

    truncated = matches[:limit]
    # Enrich each row with the doc title for easy UI rendering.
    for row in truncated:
        meta = doc_meta.get(row["doc_id"], {})
        row["title"] = meta.get("title", row["doc_id"])
        row["year"] = meta.get("year")
        row["source_type"] = meta.get("source_type")

    return {
        "query": q_clean,
        "matched_query": matched_query,
        "translit_used": translit_used,
        "total_pages": len(matches),
        "total_hits": sum(r["hits"] for r in matches),
        "docs": docs_sorted[:20],
        "results": truncated,
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
async def feedback_stats(all: int = 0) -> dict[str, Any]:
    """Stats excludes SMOKE-* entries by default (they're from the prod
    smoke-test script, not real user feedback). Pass ?all=1 to include."""
    store = getattr(app.state, "feedback", None)
    if store is None:
        raise HTTPException(503, "feedback store not initialized")
    return store.stats(include_smoke=bool(all))


@app.post("/api/query", response_model=QueryCreated)
async def create_query(req: QueryRequest) -> QueryCreated:
    text = req.query.strip()
    if not text:
        raise HTTPException(400, "empty query")
    query_id = str(ULID())
    queue: asyncio.Queue[dict[str, Any] | None] = asyncio.Queue()
    app.state.running_queries[query_id] = queue

    prior_turn: dict[str, str] | None = None
    if req.prior_query and req.prior_answer:
        # Trim the excerpt — full answers can be 3-5k chars which is wasteful
        # when the Normalizer only needs a gist to condense the follow-up.
        prior_turn = {
            "query": req.prior_query.strip()[:500],
            "answer": req.prior_answer.strip()[:1200],
        }

    # Kick off the orchestrator in the background; it publishes each
    # trace event + the final response through the queue. Task reference
    # stashed on app.state so it isn't GC'd before completion.
    task = asyncio.create_task(_run_query(query_id, text, queue, prior_turn))
    app.state.tasks.add(task)
    task.add_done_callback(app.state.tasks.discard)

    return QueryCreated(query_id=query_id, stream_url=f"/api/stream/{query_id}")


async def _run_query(
    query_id: str,
    text: str,
    queue: asyncio.Queue[dict[str, Any] | None],
    prior_turn: dict[str, str] | None = None,
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
            await orchestrator.run(text, state=state, prior_turn=prior_turn)
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


def _load_processed_chunks(rec) -> list[dict[str, Any]] | None:
    """Read the per-document processed-chunk JSON from
    catalog/processed/{source_type}/{doc_id}.json. Returns None if the
    file isn't present (e.g. document indexed but not chunked yet)."""
    p = Path("catalog/processed") / rec.source_type / f"{rec.doc_id}.json"
    if not p.exists():
        return None
    try:
        raw = json.loads(p.read_text(encoding="utf-8"))
    except Exception:
        return None
    if not isinstance(raw, list):
        return None
    # Defensive: keep only dicts with the required fields.
    clean: list[dict[str, Any]] = []
    for row in raw:
        if not isinstance(row, dict):
            continue
        if "text" not in row or "page" not in row:
            continue
        clean.append(row)
    # Stable sort: by page ascending, then by section_path for determinism.
    clean.sort(key=lambda r: (int(r.get("page", 0) or 0), str(r.get("section_path", ""))))
    return clean


# PDF-extraction noise patterns. Kemenkes guideline PDFs carry a
# vertical "KEMENTERIAN KESEHATAN" watermark; pdfplumber inlines each
# watermark glyph as a single-letter line AND occasionally splices
# watermark glyphs into the middle of words (e.g. "pasti" → "pastAi",
# "kontribusi" → "kontEribusi"). We fix it at render time, leaving
# the raw catalog chunks untouched.
#
# Critical constraint: many medical-dense tokens look like splices but
# ARE the canonical form — "mmHg", "mEq", "kPa", "cGy", "NaCl",
# "HBsAg", "HBeAg", "CrCl", gene names like "HOX11L2" and "BRAFV600E".
# The alpha splice rule therefore only fires when (a) the containing
# word is ≥6 chars AND (b) it has exactly one uppercase letter. That
# loses a handful of short-word fixes ("khaIs", "daEn") but preserves
# 1,400+ medical tokens the earlier blanket rule would destroy.
# The digit-cap-digit rule was dropped entirely after catalog audit
# showed 200 medical-code false positives vs 5 legitimate watermark
# year fixes.
_OCR_SPLICE_ALPHA_RE = re.compile(r"([a-z])([A-Z])([a-z])")
_OCR_WORD_BOUND_RE = re.compile(r"[A-Za-z0-9]+")
_OCR_PAGE_FOOTER_RE = re.compile(r"^\s*-\s*\d+\s*-\s*$")
_OCR_URL_FOOTER_RE = re.compile(r"^\s*(?:www\.)?[a-z]+\.kemkes\.go\.id\s*$", re.I)
_OCR_LONE_CAP_RE = re.compile(r"^\s*[A-Z]\s*$")
_OCR_MULTI_BLANK_RE = re.compile(r"\n{3,}")
# Trailing or leading watermark letters attached to a line: "BAB I E"
# → "BAB I", "E Pada pasien" → "Pada pasien". Exclude I/V/X/L/C/D/M
# so we don't eat roman numerals on legitimate section headers like
# "BAB I" or "DERAJAT IV".
_OCR_TRAILING_CAP_RE = re.compile(r" ([A-HJKN-UW-Z])$", re.M)
_OCR_LEADING_CAP_RE = re.compile(r"^([A-HJKN-UW-Z]) ", re.M)


def _fix_word_splice(s: str) -> str:
    """Remove watermark-letter splices from Indonesian prose, skipping
    medical abbreviations (mmHg, mEq, NaCl, HBsAg, BRAFV600E, etc.)
    by requiring the containing ALPHABETIC word (no digits) to be
    ≥6 chars AND have exactly one uppercase letter. Digits act as
    boundaries so "140/90mmHg" sees "mmHg" (4 chars, below threshold)
    rather than "90mmHg" (6 chars, over threshold)."""
    def walk_word(start: int, end: int) -> tuple[int, int]:
        ws = start
        while ws > 0 and s[ws - 1].isalpha():
            ws -= 1
        we = end
        while we < len(s) and s[we].isalpha():
            we += 1
        return ws, we

    def sub(match: re.Match[str]) -> str:
        ws, we = walk_word(match.start(), match.end())
        word = s[ws:we]
        cap_count = sum(1 for ch in word if ch.isupper())
        if cap_count != 1 or len(word) < 6:
            return match.group(0)
        return match.group(1) + match.group(3)

    return _OCR_SPLICE_ALPHA_RE.sub(sub, s)


def _clean_guideline_text(s: str) -> str:
    """Strip PDF-extraction noise from a single chunk's text.

    See _OCR_*_RE docs above for the patterns this fixes. Returns the
    cleaned text with trailing whitespace trimmed and runs of blank
    lines collapsed.
    """
    if not s:
        return s
    s = _fix_word_splice(s)
    out: list[str] = []
    for line in s.splitlines():
        # Trim dangling watermark letters first — pdfplumber sometimes
        # leaves a line like "-25- N" where the footer is followed by
        # a watermark letter; we need the trim to run before the
        # footer drop-check sees the line.
        for _ in range(3):
            new_line = _OCR_TRAILING_CAP_RE.sub("", line)
            new_line = _OCR_LEADING_CAP_RE.sub("", new_line)
            if new_line == line:
                break
            line = new_line
        if _OCR_PAGE_FOOTER_RE.match(line):
            continue
        if _OCR_URL_FOOTER_RE.match(line):
            continue
        if _OCR_LONE_CAP_RE.match(line):
            continue
        out.append(line)
    cleaned = "\n".join(out)
    cleaned = _OCR_MULTI_BLANK_RE.sub("\n\n", cleaned)
    return cleaned.strip()


def _beautify_slug(slug: str) -> str:
    """Turn a system slug like 'latar-belakang' into a display heading
    'Latar Belakang'. Returns '' for junk slugs (single letter, or
    short all-lowercase-consonant fragments like 'gy' that come from
    the same watermark-letter extraction bug) so the renderer can
    skip emitting a header."""
    s = slug.strip()
    if not s:
        return ""
    # Skip single-letter / two-letter junk. Real sections in the
    # catalog are always at least one hyphenated word (≥3 chars).
    if len(s) <= 2 and "-" not in s and "_" not in s:
        return ""
    parts = re.split(r"[-_]", s)
    return " ".join(p.capitalize() for p in parts if p)


def _render_guideline_markdown(rec, chunks: list[dict[str, Any]]) -> str:
    """Assemble a per-document Markdown. Sectioned by page so a
    doctor can cross-reference the PDF; section_path shown as a
    small header per chunk. Mobile-friendly, no dependencies."""
    lines: list[str] = []
    lines.append(f"# {rec.title}")
    lines.append("")
    lines.append(
        f"**{rec.doc_id}** · {rec.source_type.replace('_', ' ').upper()} · {rec.year}"
    )
    if rec.authority:
        lines.append(f"Penerbit: {rec.authority}")
    if rec.kepmenkes_number:
        lines.append(f"No. regulasi: {rec.kepmenkes_number}")
    lines.append("")
    lines.append(
        "> Dokumen ini diindeks oleh Anamnesa dari arsip Kemenkes RI. "
        "Basis hukum: UU 28/2014 Pasal 42 (public domain). "
        "Hanya referensi — bukan alat diagnosis."
    )
    lines.append("")
    lines.append(f"_Diekspor pada {datetime.now(UTC).isoformat()}_")
    lines.append("")
    lines.append("---")
    lines.append("")

    current_page: int | None = None
    for c in chunks:
        page = int(c.get("page", 0) or 0)
        if page != current_page:
            lines.append(f"## Halaman {page}" if page else "## Pendahuluan")
            lines.append("")
            current_page = page
        slug_raw = str(c.get("section_slug") or "").strip()
        path = str(c.get("section_path") or "").strip()
        slug_pretty = _beautify_slug(slug_raw)
        if slug_pretty:
            lines.append(f"### {slug_pretty}")
            if path and path != slug_raw and path != slug_pretty:
                lines.append(f"*{path}*")
            lines.append("")
        text = _clean_guideline_text(str(c.get("text") or ""))
        if text:
            lines.append(text)
            lines.append("")
    return "\n".join(lines)


_GUIDELINE_HTML_CSS = """
:root {
  --paper: #F7F3EC; --paper-2: #EFE8D9; --ink: #0F1B2D; --ink-2: #2A3B57;
  --ink-3: #556784; --navy: #1E2F4D; --oxblood: #8B1E2D; --rule: #D9CFB8;
  --mono: ui-monospace, "SF Mono", Menlo, monospace;
}
* { box-sizing: border-box; }
html, body {
  margin: 0;
  background: var(--paper);
  color: var(--ink);
  font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
}
body {
  padding: 24px 18px 80px;
  max-width: 780px;
  margin: 0 auto;
  line-height: 1.65;
  font-size: 16px;
  -webkit-font-smoothing: antialiased;
}
header { border-bottom: 1px solid var(--rule); padding-bottom: 16px; margin-bottom: 24px; }
h1 { font-size: 26px; margin: 0 0 8px; letter-spacing: -0.01em; line-height: 1.2; }
.meta {
  color: var(--ink-3); font-family: var(--mono); font-size: 12.5px;
  display: flex; flex-wrap: wrap; gap: 8px;
}
.meta-sep { opacity: 0.4; }
.legal {
  margin-top: 14px; padding: 10px 14px; border-left: 2px solid var(--oxblood);
  background: var(--paper-2); font-size: 13px; color: var(--ink-2);
}
.backlink {
  display: inline-block; margin-bottom: 14px; font-family: var(--mono);
  font-size: 12px; color: var(--navy); text-decoration: none; letter-spacing: 0.04em;
}
.backlink:hover { text-decoration: underline; }
.page {
  margin-top: 28px; padding-top: 14px; border-top: 1px dashed var(--rule);
  scroll-margin-top: 12px;
}
.page-label {
  font-family: var(--mono); font-size: 11px; color: var(--ink-3);
  letter-spacing: 0.14em; text-transform: uppercase; margin: 0;
}
h2 {
  margin: 2px 0 14px; font-size: 18px; color: var(--ink);
  letter-spacing: -0.01em; font-weight: 600;
}
h3 {
  margin: 18px 0 4px; font-size: 14.5px; font-family: var(--mono);
  color: var(--ink-2); letter-spacing: 0.02em; font-weight: 500;
}
.path { color: var(--ink-3); font-family: var(--mono); font-size: 11px; margin: 0 0 8px; word-break: break-all; }
p { margin: 0 0 14px; white-space: pre-wrap; word-wrap: break-word; overflow-wrap: anywhere; }
.to-top {
  position: fixed; bottom: 14px; right: 14px;
  padding: 8px 12px; background: var(--navy); color: var(--paper);
  text-decoration: none; font-family: var(--mono); font-size: 12px;
  border-radius: 2px; box-shadow: 0 2px 8px rgba(0,0,0,0.12);
  opacity: 0.85;
}
.to-top:hover { opacity: 1; }
footer {
  margin-top: 48px; padding-top: 16px; border-top: 1px solid var(--rule);
  color: var(--ink-3); font-size: 12px; text-align: center;
}
@media (prefers-color-scheme: dark) {
  :root {
    --paper: #0B1220; --paper-2: #121B2E; --ink: #E8E2D4;
    --ink-2: #B8B0A0; --ink-3: #8A8372; --navy: #8AA5D8; --oxblood: #E0727E;
    --rule: #26324A;
  }
}
""".strip()


def _render_guideline_html(rec, chunks: list[dict[str, Any]]) -> str:
    """Self-contained HTML. No external fonts or scripts — works on a
    Puskesmas network, on iOS Safari, without the PDF iframe quirks."""
    import html as html_lib

    def esc(s: str) -> str:
        return html_lib.escape(s, quote=True)

    # Group chunks by page so we can render one <section> per page
    # with an id anchor. 900+ pages is a lot — the TOC at the top
    # gives the user a jump index.
    pages: list[tuple[int, list[dict[str, Any]]]] = []
    current_page: int | None = None
    for c in chunks:
        page = int(c.get("page", 0) or 0)
        if page != current_page:
            pages.append((page, [c]))
            current_page = page
        else:
            pages[-1][1].append(c)

    # Header
    meta_bits: list[str] = [
        f"<span>{esc(rec.doc_id)}</span>",
        f'<span class="meta-sep">·</span>',
        f"<span>{esc(rec.source_type.replace('_', ' ').upper())}</span>",
        f'<span class="meta-sep">·</span>',
        f"<span>{rec.year}</span>",
    ]
    if rec.authority:
        meta_bits += [
            '<span class="meta-sep">·</span>',
            f"<span>{esc(rec.authority)}</span>",
        ]
    if rec.kepmenkes_number:
        meta_bits += [
            '<span class="meta-sep">·</span>',
            f"<span>{esc(rec.kepmenkes_number)}</span>",
        ]

    parts: list[str] = []
    parts.append("<!DOCTYPE html>\n<html lang=\"id\">\n<head>\n")
    parts.append('<meta charset="utf-8">\n')
    parts.append('<meta name="viewport" content="width=device-width, initial-scale=1">\n')
    parts.append(f"<title>{esc(rec.title)} — Anamnesa</title>\n")
    parts.append(f"<style>\n{_GUIDELINE_HTML_CSS}\n</style>\n")
    parts.append("</head>\n<body>\n")
    parts.append('<a class="backlink" href="/guideline">← Kembali ke pustaka</a>\n')
    parts.append('<header id="top">\n')
    parts.append(f"<h1>{esc(rec.title)}</h1>\n")
    parts.append(f'<div class="meta">{"".join(meta_bits)}</div>\n')
    parts.append(
        '<div class="legal">Diindeks oleh Anamnesa dari arsip Kemenkes RI. '
        "Basis hukum: <strong>UU 28/2014 Pasal 42</strong> (public domain). "
        "Hanya referensi — bukan alat diagnosis.</div>\n"
    )
    parts.append("</header>\n")

    for page_num, page_chunks in pages:
        anchor = f"p{page_num}" if page_num else "p0"
        page_label = f"HALAMAN {page_num}" if page_num else "PENDAHULUAN"
        parts.append(f'<section class="page" id="{anchor}">\n')
        parts.append(f'<div class="page-label">{page_label}</div>\n')
        # First chunk on this page: use its section_slug as the h2.
        first = page_chunks[0]
        first_slug_pretty = _beautify_slug(str(first.get("section_slug") or ""))
        if first_slug_pretty:
            parts.append(f"<h2>{esc(first_slug_pretty)}</h2>\n")
        for i, chunk in enumerate(page_chunks):
            slug_raw = str(chunk.get("section_slug") or "").strip()
            slug_pretty = _beautify_slug(slug_raw)
            path = str(chunk.get("section_path") or "").strip()
            text = _clean_guideline_text(str(chunk.get("text") or ""))
            # Use h3 for subsequent section slugs within the same page.
            if i > 0 and slug_pretty:
                parts.append(f"<h3>{esc(slug_pretty)}</h3>\n")
            # Show the full hierarchical path only when it adds info
            # beyond the heading we just rendered — avoids the ugly
            # h3 "Latar Belakang" / path "bab_1/latar-belakang" dupe.
            # Also skip when the slug itself was junk (single-letter
            # watermark) since the path's last segment is the same junk.
            if (
                slug_pretty
                and path
                and path != slug_raw
                and path.lower() != slug_pretty.lower()
                and "/" in path
            ):
                parts.append(f'<div class="path">{esc(path)}</div>\n')
            if text:
                parts.append(f"<p>{esc(text)}</p>\n")
        parts.append("</section>\n")

    parts.append('<a class="to-top" href="#top">↑ atas</a>\n')
    parts.append(
        f'<footer>Diekspor dari anamnesa.kudaliar.id · {datetime.now(UTC).isoformat()}</footer>\n'
    )
    parts.append("</body>\n</html>\n")
    return "".join(parts)


@app.get("/api/guideline/{doc_id}.md", response_class=PlainTextResponse)
async def guideline_markdown(doc_id: str) -> PlainTextResponse:
    m: Manifest = app.state.manifest
    rec = next((d for d in m.documents if d.doc_id == doc_id), None)
    if rec is None:
        raise HTTPException(404, f"unknown doc_id: {doc_id!r}")
    chunks = _load_processed_chunks(rec)
    if chunks is None:
        raise HTTPException(404, f"no processed chunks for {doc_id!r}")
    body = _render_guideline_markdown(rec, chunks)
    return PlainTextResponse(
        body,
        media_type="text/markdown; charset=utf-8",
        headers={"Content-Disposition": f'attachment; filename="{doc_id}.md"'},
    )


@app.get("/api/guideline/{doc_id}.html", response_class=Response)
async def guideline_html(doc_id: str) -> Response:
    m: Manifest = app.state.manifest
    rec = next((d for d in m.documents if d.doc_id == doc_id), None)
    if rec is None:
        raise HTTPException(404, f"unknown doc_id: {doc_id!r}")
    chunks = _load_processed_chunks(rec)
    if chunks is None:
        raise HTTPException(404, f"no processed chunks for {doc_id!r}")
    body = _render_guideline_html(rec, chunks)
    return Response(
        content=body,
        media_type="text/html; charset=utf-8",
    )


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
