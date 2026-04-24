"""LanceDB-backed chunk store for Anamnesa retrieval.

This is a thin wrapper over a single LanceDB table (`chunks`). The store owns
persistence and vector search; BM25 is layered on top in `core/retrieval.py`.

Schema of the `chunks` table:

    doc_id:       string    # ManifestRecord.doc_id
    page:         int32
    section_slug: string
    section_path: string
    text:         string
    year:         int32
    source_type:  string    # one of state.SourceType
    source_url:   string    # "" when None (Lance does not love nullable here)
    row_key:      string    # f"{doc_id}::{page}::{section_slug}" — upsert key
    vector:       fixed-size list[float32]  # len == Embedder.dim

The upsert key combines `(doc_id, page, section_slug)`. Re-ingesting the same
chunk with updated text replaces the prior row rather than duplicating it.
"""

from __future__ import annotations

import os
from collections.abc import Iterator
from dataclasses import dataclass
from pathlib import Path

import lancedb
import pyarrow as pa
import structlog
from lancedb.db import DBConnection
from lancedb.table import Table

from core.state import Chunk

log = structlog.get_logger("anamnesa.retrieval")

TABLE_NAME = "chunks"
DEFAULT_LANCE_PATH = Path("./index/lance")


def _default_path() -> Path:
    env = os.environ.get("LANCE_DB_PATH")
    return Path(env) if env else DEFAULT_LANCE_PATH


@dataclass(frozen=True, slots=True)
class StoredChunk:
    """A Chunk plus the vector to persist with it."""

    chunk: Chunk
    vector: list[float]


def _row_key(doc_id: str, page: int, section_slug: str) -> str:
    return f"{doc_id}::{page}::{section_slug}"


def _schema(dim: int) -> pa.Schema:
    return pa.schema(
        [
            pa.field("doc_id", pa.string(), nullable=False),
            pa.field("page", pa.int32(), nullable=False),
            pa.field("section_slug", pa.string(), nullable=False),
            pa.field("section_path", pa.string(), nullable=False),
            pa.field("text", pa.string(), nullable=False),
            pa.field("year", pa.int32(), nullable=False),
            pa.field("source_type", pa.string(), nullable=False),
            pa.field("source_url", pa.string(), nullable=False),
            pa.field("row_key", pa.string(), nullable=False),
            pa.field("vector", pa.list_(pa.float32(), dim), nullable=False),
        ]
    )


def _row_from_stored(sc: StoredChunk) -> dict[str, object]:
    c = sc.chunk
    return {
        "doc_id": c.doc_id,
        "page": int(c.page),
        "section_slug": c.section_slug,
        "section_path": c.section_path,
        "text": c.text,
        "year": int(c.year),
        "source_type": c.source_type,
        "source_url": c.source_url or "",
        "row_key": _row_key(c.doc_id, c.page, c.section_slug),
        "vector": [float(v) for v in sc.vector],
    }


def _chunk_from_row(row: dict[str, object]) -> Chunk:
    return Chunk(
        doc_id=str(row["doc_id"]),
        page=int(row["page"]),  # type: ignore[arg-type]
        section_slug=str(row["section_slug"]),
        section_path=str(row["section_path"]),
        text=str(row["text"]),
        year=int(row["year"]),  # type: ignore[arg-type]
        source_type=str(row["source_type"]),  # type: ignore[arg-type]
        score=float(row.get("_score", 0.0)),  # type: ignore[arg-type]
        source_url=(str(row["source_url"]) or None),
    )


def _escape_sql(value: str) -> str:
    """Escape a single-quoted SQL literal (LanceDB uses SQL-like predicates)."""
    return value.replace("'", "''")


def _list_table_names(db: DBConnection) -> list[str]:
    """Normalize LanceDB `list_tables()` across versions (object-with-.tables vs. iterable)."""
    result = db.list_tables()
    tables_attr = getattr(result, "tables", None)
    if tables_attr is not None:
        return [str(t) for t in tables_attr]
    try:
        return [str(t) for t in result]  # type: ignore[arg-type]
    except TypeError:
        return []


class LanceChunkStore:
    """Thin, synchronous wrapper around a single LanceDB table."""

    def __init__(self, db_path: Path | str | None = None) -> None:
        self._db_path = Path(db_path) if db_path is not None else _default_path()
        self._db_path.mkdir(parents=True, exist_ok=True)
        self._db: DBConnection = lancedb.connect(str(self._db_path))
        self._table: Table | None = None
        if TABLE_NAME in _list_table_names(self._db):
            self._table = self._db.open_table(TABLE_NAME)

    @property
    def db_path(self) -> Path:
        return self._db_path

    @property
    def table(self) -> Table | None:
        return self._table

    def upsert(self, items: list[StoredChunk]) -> None:
        if not items:
            return
        dim = len(items[0].vector)
        if any(len(it.vector) != dim for it in items):
            raise ValueError("all StoredChunk.vector must share the same length")

        rows = [_row_from_stored(it) for it in items]

        if self._table is None:
            self._table = self._db.create_table(
                TABLE_NAME, data=rows, schema=_schema(dim)
            )
            log.info("chunk_store.created", path=str(self._db_path), rows=len(rows))
            return

        keys = {str(r["row_key"]) for r in rows}
        if keys:
            quoted = ", ".join(f"'{_escape_sql(k)}'" for k in keys)
            self._table.delete(f"row_key IN ({quoted})")
        self._table.add(rows)
        log.info(
            "chunk_store.upsert",
            path=str(self._db_path),
            upserted=len(rows),
            keys=len(keys),
        )

    def delete_by_doc_id(self, doc_id: str) -> None:
        if self._table is None:
            return
        self._table.delete(f"doc_id = '{_escape_sql(doc_id)}'")
        log.info("chunk_store.deleted", doc_id=doc_id)

    def iter_chunks(self) -> Iterator[Chunk]:
        if self._table is None:
            return
        rows = self._table.to_arrow().to_pylist()
        for row in rows:
            yield _chunk_from_row(row)

    def count(self) -> int:
        if self._table is None:
            return 0
        return int(self._table.count_rows())

    def search_vector(
        self,
        vector: list[float],
        k: int,
        *,
        where: str | None = None,
    ) -> list[Chunk]:
        """Approximate-NN search. Returns `k` nearest chunks.

        LanceDB returns an internal `_distance`. We invert it into a score
        where larger == more similar, exposed via `Chunk.score`.
        """
        if self._table is None or self._table.count_rows() == 0:
            return []
        q = self._table.search(vector).limit(max(k, 1))
        if where:
            q = q.where(where)
        raw = q.to_list()
        out: list[Chunk] = []
        for row in raw:
            distance = float(row.get("_distance", 0.0))
            score = 1.0 / (1.0 + distance)
            row["_score"] = score
            out.append(_chunk_from_row(row))
        return out

    @property
    def vector_dim(self) -> int | None:
        if self._table is None:
            return None
        for f in self._table.schema:
            if f.name == "vector":
                t = f.type
                if pa.types.is_fixed_size_list(t):
                    return int(t.list_size)
        return None
