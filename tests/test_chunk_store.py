"""Tests for the LanceDB-backed chunk store.

Uses a tmp_path LanceDB directory and the deterministic HashEmbedder so no
external embedding service is required.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from core.chunk_store import LanceChunkStore, StoredChunk
from core.embeddings import HashEmbedder
from core.state import Chunk


def _make_chunk(
    *,
    doc_id: str = "ppk-fktp-2015",
    page: int = 1,
    section_slug: str = "s",
    text: str = "contoh teks pedoman",
    year: int = 2015,
    source_type: str = "ppk_fktp",
) -> Chunk:
    return Chunk(
        doc_id=doc_id,
        page=page,
        section_slug=section_slug,
        section_path=f"{doc_id}/{section_slug}",
        text=text,
        year=year,
        source_type=source_type,  # type: ignore[arg-type]
        score=0.0,
    )


@pytest.fixture()
def store(tmp_path: Path) -> LanceChunkStore:
    return LanceChunkStore(db_path=tmp_path / "lance")


@pytest.fixture()
def embedder() -> HashEmbedder:
    return HashEmbedder(dim=64)


def test_upsert_and_iterate_single_chunk(
    store: LanceChunkStore, embedder: HashEmbedder
) -> None:
    chunk = _make_chunk(text="terapi cairan kristaloid pada DBD")
    vec = embedder.embed([chunk.text])[0]
    store.upsert([StoredChunk(chunk=chunk, vector=vec)])

    all_chunks = list(store.iter_chunks())
    assert len(all_chunks) == 1
    assert all_chunks[0].doc_id == chunk.doc_id
    assert all_chunks[0].text == chunk.text


def test_upsert_replaces_existing_rows_for_same_doc(
    store: LanceChunkStore, embedder: HashEmbedder
) -> None:
    original = _make_chunk(page=1, text="versi lama")
    updated = _make_chunk(page=1, text="versi baru")

    store.upsert([StoredChunk(chunk=original, vector=embedder.embed([original.text])[0])])
    store.upsert([StoredChunk(chunk=updated, vector=embedder.embed([updated.text])[0])])

    chunks = list(store.iter_chunks())
    assert len(chunks) == 1
    assert chunks[0].text == "versi baru"


def test_delete_by_doc_id(store: LanceChunkStore, embedder: HashEmbedder) -> None:
    a = _make_chunk(doc_id="a", page=1, text="dokumen a halaman 1")
    b = _make_chunk(doc_id="b", page=1, text="dokumen b halaman 1")
    store.upsert(
        [
            StoredChunk(chunk=a, vector=embedder.embed([a.text])[0]),
            StoredChunk(chunk=b, vector=embedder.embed([b.text])[0]),
        ]
    )

    store.delete_by_doc_id("a")
    remaining = list(store.iter_chunks())
    assert len(remaining) == 1
    assert remaining[0].doc_id == "b"


def test_vector_search_returns_nearest_first(
    store: LanceChunkStore, embedder: HashEmbedder
) -> None:
    chunks = [
        _make_chunk(doc_id="a", page=1, text="DBD derajat II pediatrik cairan kristaloid"),
        _make_chunk(doc_id="b", page=1, text="tuberkulosis paru OAT kategori satu"),
        _make_chunk(doc_id="c", page=1, text="hipertensi dewasa target tekanan darah"),
    ]
    store.upsert(
        [StoredChunk(chunk=c, vector=embedder.embed([c.text])[0]) for c in chunks]
    )

    query_vec = embedder.embed(["DBD derajat II pediatrik cairan kristaloid"])[0]
    hits = store.search_vector(query_vec, k=3)

    assert len(hits) == 3
    assert hits[0].doc_id == "a"


def test_persistence_across_instances(tmp_path: Path, embedder: HashEmbedder) -> None:
    path = tmp_path / "lance"
    a = _make_chunk(doc_id="a", page=1, text="persistent doc")

    store1 = LanceChunkStore(db_path=path)
    store1.upsert([StoredChunk(chunk=a, vector=embedder.embed([a.text])[0])])

    store2 = LanceChunkStore(db_path=path)
    chunks = list(store2.iter_chunks())
    assert len(chunks) == 1
    assert chunks[0].doc_id == "a"
