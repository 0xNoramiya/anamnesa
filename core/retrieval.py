"""Hybrid retrieval for Anamnesa — LanceDB vector + rank-bm25 fused with RRF.

This module is the single in-process retrieval primitive. The MCP server in
`mcp/anamnesa_mcp.py` exposes a thin tool surface over it; the `LocalRetriever`
in `mcp/client.py` wraps it as the `Retriever` Protocol from `agents/base.py`
for in-process use by the Drafter and Verifier.

Design decisions:

- **RRF (reciprocal rank fusion)** is the default fusion. It is the simplest
  and strongest baseline when the two ranker scales are not comparable; we
  weight the two lists equally unless the caller passes `retrieval_method`.
- **BM25 lives in memory** alongside a pickled sidecar at `BM25_INDEX_PATH`
  (default `./index/bm25.pkl`). LanceDB owns vectors; we own lexical.
- **Metadata filters** are pushed down into LanceDB where cheap
  (`doc_ids`, `source_types`, `min_year`, `max_year`) and applied in-Python
  for looser matches (`conditions` matched against `section_path`/`text`,
  `section_types` matched against `section_slug`).
- **Supersession** reads `catalog/manifest.json` directly. "aging" is defined
  as source_year + 5 < today's year (today is considered constant per process
  run via `date.today()`).
"""

from __future__ import annotations

import os
import pickle
from collections import defaultdict
from collections.abc import Iterable
from datetime import date
from pathlib import Path
from typing import Any

import structlog
from rank_bm25 import BM25Okapi

from core.text_cleanup import clean_guideline_text

from core.chunk_store import LanceChunkStore
from core.embeddings import Embedder
from core.manifest import Manifest
from core.state import Chunk, NormalizedQuery, RetrievalFilters, SourceType

log = structlog.get_logger("anamnesa.retrieval")

DEFAULT_BM25_PATH = Path("./index/bm25.pkl")
DEFAULT_MANIFEST_PATH = Path("./catalog/manifest.json")
AGING_THRESHOLD_YEARS = 5
RRF_K = 60  # standard RRF constant — insensitive to reasonable values


def _bm25_path_from_env() -> Path:
    env = os.environ.get("BM25_INDEX_PATH")
    return Path(env) if env else DEFAULT_BM25_PATH


def _manifest_path_from_env() -> Path:
    env = os.environ.get("ANAMNESA_MANIFEST_PATH")
    return Path(env) if env else DEFAULT_MANIFEST_PATH


def _tokenize(text: str) -> list[str]:
    """Shared tokenizer for BM25. Keep in sync with `embeddings._tokenize`.

    BM25 does not need stemming for the hackathon corpus; strings are short
    and domain-specific. We simply lowercase and split on non-word chars.
    """
    import re

    return [t.lower() for t in re.findall(r"[A-Za-z0-9\u00C0-\u024F]+", text, re.UNICODE)]


def _chunk_key(c: Chunk) -> str:
    """Stable identity for fusion — must match row_key in chunk_store."""
    return f"{c.doc_id}::{c.page}::{c.section_slug}"


def _clean_chunk(c: Chunk) -> Chunk:
    """Return a copy of `c` with watermark/footer noise stripped from
    its body text. Cheap pure function; run on every retrieval result
    so the Drafter never sees raw PDF-extraction artifacts."""
    cleaned = clean_guideline_text(c.text)
    if cleaned == c.text:
        return c
    return c.model_copy(update={"text": cleaned})


def _chunk_matches_filters(chunk: Chunk, filters: RetrievalFilters) -> bool:
    if filters.doc_ids and chunk.doc_id not in filters.doc_ids:
        return False
    if filters.source_types and chunk.source_type not in filters.source_types:
        return False
    if filters.min_year is not None and chunk.year < filters.min_year:
        return False
    if filters.max_year is not None and chunk.year > filters.max_year:
        return False
    if filters.section_types:
        if not any(
            t.lower() in chunk.section_slug.lower() for t in filters.section_types
        ):
            return False
    if filters.conditions:
        hay = f"{chunk.section_path} {chunk.text}".lower()
        if not any(cond.lower() in hay for cond in filters.conditions):
            return False
    return True


def _where_clause(filters: RetrievalFilters) -> str | None:
    """Push cheap filters down into LanceDB's SQL-like predicate layer.

    Only the cleanly-indexed filters (doc_id, source_type, year) are pushed
    down; free-text filters (conditions, section_types) are applied in
    Python so they can match against `section_path`/`section_slug`
    substrings rather than exact equality.
    """
    parts: list[str] = []
    if filters.doc_ids:
        quoted = ", ".join(f"'{d.replace(chr(39), chr(39) * 2)}'" for d in filters.doc_ids)
        parts.append(f"doc_id IN ({quoted})")
    if filters.source_types:
        quoted = ", ".join(
            f"'{s.replace(chr(39), chr(39) * 2)}'" for s in filters.source_types
        )
        parts.append(f"source_type IN ({quoted})")
    if filters.min_year is not None:
        parts.append(f"year >= {int(filters.min_year)}")
    if filters.max_year is not None:
        parts.append(f"year <= {int(filters.max_year)}")
    if not parts:
        return None
    return " AND ".join(parts)


class HybridRetriever:
    """Vector + BM25 hybrid retriever with reciprocal-rank fusion.

    One process, one store, one BM25 index. Safe to construct per-request;
    BM25 load is O(file size) and LanceDB connection is cheap.
    """

    def __init__(
        self,
        *,
        store: LanceChunkStore,
        embedder: Embedder,
        manifest_path: Path | str | None = None,
        bm25_path: Path | str | None = None,
    ) -> None:
        self.store = store
        self.embedder = embedder
        self.manifest_path: Path = (
            Path(manifest_path) if manifest_path is not None else _manifest_path_from_env()
        )
        self.bm25_path: Path = (
            Path(bm25_path) if bm25_path is not None else _bm25_path_from_env()
        )
        self._bm25: BM25Okapi | None = None
        self._bm25_chunks: list[Chunk] = []
        self._manifest_cache: Manifest | None = None

    # -- BM25 ------------------------------------------------------------

    def rebuild_bm25_from_store(self) -> None:
        chunks = list(self.store.iter_chunks())
        self._bm25_chunks = chunks
        if not chunks:
            self._bm25 = None
            return
        self._bm25 = BM25Okapi([_tokenize(c.text) for c in chunks])
        log.info("retrieval.bm25_rebuilt", chunks=len(chunks))

    def save_bm25(self) -> None:
        self.bm25_path.parent.mkdir(parents=True, exist_ok=True)
        payload = {
            "chunks": [c.model_dump() for c in self._bm25_chunks],
            # BM25Okapi itself pickles cleanly.
            "bm25": self._bm25,
        }
        with self.bm25_path.open("wb") as fh:
            pickle.dump(payload, fh)
        log.info("retrieval.bm25_saved", path=str(self.bm25_path))

    def load_bm25(self) -> None:
        if not self.bm25_path.exists():
            log.info("retrieval.bm25_missing", path=str(self.bm25_path))
            self._bm25 = None
            self._bm25_chunks = []
            return
        with self.bm25_path.open("rb") as fh:
            payload = pickle.load(fh)
        self._bm25_chunks = [Chunk(**d) for d in payload["chunks"]]
        self._bm25 = payload["bm25"]
        log.info("retrieval.bm25_loaded", chunks=len(self._bm25_chunks))

    def bm25_search(self, query: str, k: int) -> list[Chunk]:
        if self._bm25 is None or not self._bm25_chunks:
            return []
        tokens = _tokenize(query)
        if not tokens:
            return []
        scores = self._bm25.get_scores(tokens)
        # Rank by score desc
        order = sorted(
            range(len(scores)),
            key=lambda i: scores[i],
            reverse=True,
        )
        out: list[Chunk] = []
        for i in order[:k]:
            if scores[i] <= 0.0:
                continue
            src = self._bm25_chunks[i]
            out.append(
                src.model_copy(
                    update={"score": float(scores[i]), "retrieval_method": "bm25"}
                )
            )
        return out

    # -- vector ----------------------------------------------------------

    def vector_search(
        self, query: str, k: int, *, where: str | None = None
    ) -> list[Chunk]:
        # Prefer query-mode embedding when the embedder supports it
        # (BGE-M3 recommends a "query: " prefix for queries). Falls back
        # to `embed()` for embedders without the distinction (HashEmbedder).
        encode_query = getattr(self.embedder, "embed_queries", None)
        if callable(encode_query):
            vec = encode_query([query])[0]
        else:
            vec = self.embedder.embed([query])[0]
        hits = self.store.search_vector(vec, k, where=where)
        return [c.model_copy(update={"retrieval_method": "vector"}) for c in hits]

    # -- hybrid fusion ---------------------------------------------------

    def search_guidelines(
        self, query: NormalizedQuery, filters: RetrievalFilters
    ) -> list[Chunk]:
        """Public entry point. Returns the final ranked chunks."""

        query_text = _compose_query_text(query)
        top_k = max(1, int(filters.top_k))
        # Over-fetch per list so fusion has headroom and filters leave room.
        per_list_k = max(top_k * 3, 20)

        where = _where_clause(filters)

        vector_hits = self.vector_search(query_text, per_list_k, where=where)
        bm25_hits = self.bm25_search(query_text, per_list_k)

        # Apply python-level filters uniformly
        vector_hits = [c for c in vector_hits if _chunk_matches_filters(c, filters)]
        bm25_hits = [c for c in bm25_hits if _chunk_matches_filters(c, filters)]

        fused = _rrf_fuse([vector_hits, bm25_hits])

        log.info(
            "retrieval.searched",
            query=query.structured_query[:80],
            vector_hits=len(vector_hits),
            bm25_hits=len(bm25_hits),
            fused=len(fused),
            filters=filters.model_dump(exclude_none=True),
        )
        # Strip PDF-extraction noise (watermark splices, page footers)
        # so the Drafter reads clean Indonesian prose. Raw BM25/vector
        # scores are preserved; only the text body changes. See
        # core/text_cleanup for the rule set and safety constraints.
        return [_clean_chunk(c) for c in fused[:top_k]]

    # -- supporting tools ------------------------------------------------

    def get_full_section(self, doc_id: str, section_path: str) -> dict[str, Any]:
        """Return the stored text for the chunk whose section_path matches.

        If multiple chunks share the section_path (multi-page sections), the
        texts are concatenated in page order.
        """
        matches: list[Chunk] = []
        for c in self.store.iter_chunks():
            if c.doc_id == doc_id and c.section_path == section_path:
                matches.append(c)
        if not matches:
            raise KeyError(f"no chunk for ({doc_id!r}, {section_path!r})")
        matches.sort(key=lambda c: c.page)
        text = "\n\n".join(clean_guideline_text(m.text) for m in matches)
        return {
            "doc_id": doc_id,
            "section_path": section_path,
            "text": text,
        }

    def get_pdf_page_url(self, doc_id: str, page: int) -> str:
        origin = os.environ.get("ANAMNESA_PUBLIC_ORIGIN", "").strip()
        if origin:
            return f"{origin.rstrip('/')}/pdf/{doc_id}.pdf#page={page}"
        # Local: point at the cached PDF when the manifest knows about it.
        manifest = self._load_manifest()
        if manifest is not None:
            for rec in manifest.documents:
                if rec.doc_id == doc_id and rec.cache_path:
                    cache = Path(rec.cache_path).resolve()
                    return f"file://{cache}#page={page}"
        # Fallback for chunks whose manifest entry has no cache_path.
        return f"file:///{doc_id}.pdf#page={page}"

    def check_supersession(self, doc_id: str) -> dict[str, Any]:
        manifest = self._load_manifest()
        if manifest is None:
            return {"status": "unknown", "superseding_doc_id": None, "source_year": 0}
        for rec in manifest.documents:
            if rec.doc_id != doc_id:
                continue
            if rec.superseded_by:
                return {
                    "status": "superseded",
                    "superseding_doc_id": rec.superseded_by[0],
                    "source_year": rec.year,
                }
            today = date.today()
            if rec.year + AGING_THRESHOLD_YEARS < today.year:
                return {
                    "status": "aging",
                    "superseding_doc_id": None,
                    "source_year": rec.year,
                }
            return {
                "status": "current",
                "superseding_doc_id": None,
                "source_year": rec.year,
            }
        return {"status": "unknown", "superseding_doc_id": None, "source_year": 0}

    # -- internals -------------------------------------------------------

    def _load_manifest(self) -> Manifest | None:
        if self._manifest_cache is not None:
            return self._manifest_cache
        if not self.manifest_path.exists():
            return None
        raw = self.manifest_path.read_text(encoding="utf-8")
        self._manifest_cache = Manifest.model_validate_json(raw)
        return self._manifest_cache


# ---------------------------------------------------------------------------
# Fusion
# ---------------------------------------------------------------------------


def _compose_query_text(query: NormalizedQuery) -> str:
    parts: list[str] = [query.structured_query]
    parts.extend(query.keywords_id)
    parts.extend(query.keywords_en)
    parts.extend(query.condition_tags)
    return " ".join(p for p in parts if p)


def _rrf_fuse(
    ranked_lists: Iterable[list[Chunk]], *, k_const: int = RRF_K
) -> list[Chunk]:
    """Reciprocal rank fusion over multiple ranked lists.

    RRF score for a doc d = sum over lists L of 1 / (k_const + rank_L(d)).
    Returns a single ranked list with Chunk.score set to the fused score and
    retrieval_method = "hybrid".
    """
    scores: dict[str, float] = defaultdict(float)
    first_seen: dict[str, Chunk] = {}

    for ranked in ranked_lists:
        for rank, chunk in enumerate(ranked):
            key = _chunk_key(chunk)
            scores[key] += 1.0 / (k_const + rank + 1)  # 1-based rank
            if key not in first_seen:
                first_seen[key] = chunk

    ordered_keys = sorted(scores.keys(), key=lambda k: scores[k], reverse=True)
    out: list[Chunk] = []
    for key in ordered_keys:
        base = first_seen[key]
        out.append(
            base.model_copy(
                update={"score": float(scores[key]), "retrieval_method": "hybrid"}
            )
        )
    return out


# ---------------------------------------------------------------------------
# Wiring helpers
# ---------------------------------------------------------------------------


def default_retriever(
    *,
    embedder: Embedder | None = None,
    manifest_path: Path | str | None = None,
    bm25_path: Path | str | None = None,
    lance_path: Path | str | None = None,
    load_bm25: bool = True,
) -> HybridRetriever:
    """Build a `HybridRetriever` from env defaults.

    Used by the MCP server's `serve()` entrypoint and by scripts. The
    embedder is selected by the `ANAMNESA_EMBEDDER` env var (`hash` or
    `bge-m3`), defaulting to `hash` so test/dev environments without the
    heavy `sentence-transformers` dep still work.
    """
    from core.embeddings import build_embedder

    if embedder is None:
        name = os.environ.get("ANAMNESA_EMBEDDER", "hash")
        emb: Embedder = build_embedder(name)
    else:
        emb = embedder
    store = LanceChunkStore(db_path=lance_path)
    r = HybridRetriever(
        store=store,
        embedder=emb,
        manifest_path=manifest_path,
        bm25_path=bm25_path,
    )
    if load_bm25:
        r.load_bm25()
    return r


__all__ = [
    "AGING_THRESHOLD_YEARS",
    "DEFAULT_BM25_PATH",
    "DEFAULT_MANIFEST_PATH",
    "HybridRetriever",
    "SourceType",
    "default_retriever",
]
