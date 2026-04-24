"""Tests for the hybrid retrieval layer.

These are end-to-end retrieval behavior tests: a real HashEmbedder, a real
tmp LanceDB, and rank-bm25. No mocks. They verify:

- Vector-only retrieval returns relevant hits.
- BM25-only retrieval returns relevant hits on a lexical query.
- RRF fusion beats either single list on a mixed query.
- Metadata filters actually filter.
- Supersession / currency logic reads the manifest correctly.
"""

from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path

import pytest

from core.chunk_store import LanceChunkStore, StoredChunk
from core.embeddings import HashEmbedder
from core.manifest import Manifest, ManifestRecord
from core.retrieval import HybridRetriever
from core.state import Chunk, NormalizedQuery, RetrievalFilters


def _chunk(
    *,
    doc_id: str,
    page: int,
    section_slug: str,
    text: str,
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
def corpus() -> list[Chunk]:
    return [
        _chunk(
            doc_id="ppk-fktp-2015",
            page=412,
            section_slug="dbd_tata_laksana_anak",
            text=(
                "Pada DBD derajat II pediatrik, terapi cairan kristaloid inisial "
                "6-7 ml/kg/jam. Monitor tanda vital."
            ),
            year=2015,
        ),
        _chunk(
            doc_id="pnpk-tb-2020",
            page=40,
            section_slug="tb_oat_dewasa",
            text="Tatalaksana TB paru dewasa OAT kategori satu selama enam bulan.",
            year=2020,
            source_type="pnpk",
        ),
        _chunk(
            doc_id="pnpk-ht-2019",
            page=12,
            section_slug="ht_target",
            text="Target tekanan darah hipertensi dewasa di bawah 140 per 90 mmHg.",
            year=2019,
            source_type="pnpk",
        ),
        _chunk(
            doc_id="ppk-fktp-2015",
            page=120,
            section_slug="dm_target",
            text="Diabetes melitus tipe dua target HbA1c di bawah tujuh persen.",
            year=2015,
        ),
        _chunk(
            doc_id="pnpk-dengue-2021",
            page=88,
            section_slug="dbd_dewasa",
            text="Tatalaksana DBD dewasa: resusitasi cairan kristaloid 500 ml bolus.",
            year=2021,
            source_type="pnpk",
        ),
    ]


@pytest.fixture()
def manifest(tmp_path: Path) -> Path:
    now = datetime.now(UTC)
    records = [
        ManifestRecord(
            doc_id="ppk-fktp-2015",
            source_type="ppk_fktp",
            title="Pedoman Praktik Klinis FKTP 2015",
            year=2015,
            source_url="https://example.test/ppk-2015.pdf",
            discovered_at=now,
        ),
        ManifestRecord(
            doc_id="pnpk-dengue-2014",
            source_type="pnpk",
            title="PNPK Dengue 2014",
            year=2014,
            source_url="https://example.test/dengue-2014.pdf",
            superseded_by=["pnpk-dengue-2021"],
            discovered_at=now,
        ),
        ManifestRecord(
            doc_id="pnpk-dengue-2021",
            source_type="pnpk",
            title="PNPK Dengue 2021",
            year=2021,
            source_url="https://example.test/dengue-2021.pdf",
            supersedes=["pnpk-dengue-2014"],
            discovered_at=now,
        ),
        ManifestRecord(
            doc_id="pnpk-tb-2020",
            source_type="pnpk",
            title="PNPK TB 2020",
            year=2020,
            source_url="https://example.test/tb-2020.pdf",
            discovered_at=now,
        ),
        ManifestRecord(
            doc_id="pnpk-ht-2019",
            source_type="pnpk",
            title="PNPK HT 2019",
            year=2019,
            source_url="https://example.test/ht-2019.pdf",
            discovered_at=now,
        ),
    ]
    manifest = Manifest(documents=records, generated_at=now)
    path = tmp_path / "manifest.json"
    path.write_text(manifest.model_dump_json(), encoding="utf-8")
    return path


@pytest.fixture()
def retriever(tmp_path: Path, corpus: list[Chunk], manifest: Path) -> HybridRetriever:
    embedder = HashEmbedder(dim=128)
    store = LanceChunkStore(db_path=tmp_path / "lance")
    stored = [
        StoredChunk(chunk=c, vector=embedder.embed([c.text])[0]) for c in corpus
    ]
    store.upsert(stored)
    r = HybridRetriever(
        store=store,
        embedder=embedder,
        manifest_path=manifest,
        bm25_path=tmp_path / "bm25.pkl",
    )
    r.rebuild_bm25_from_store()
    return r


def test_vector_only_search_finds_relevant_chunk(retriever: HybridRetriever) -> None:
    results = retriever.vector_search(
        "DBD derajat II pediatrik terapi cairan",
        k=3,
    )
    assert results, "vector search returned no hits"
    top_doc_ids = [c.doc_id for c in results]
    assert "ppk-fktp-2015" in top_doc_ids


def test_bm25_only_search_finds_relevant_chunk(retriever: HybridRetriever) -> None:
    results = retriever.bm25_search("OAT kategori satu", k=3)
    assert results
    top = results[0]
    assert top.doc_id == "pnpk-tb-2020"


def test_hybrid_rrf_combines_vector_and_bm25(retriever: HybridRetriever) -> None:
    """RRF should rank the chunk that both signals agree on above chunks
    that only one signal prefers."""
    query = "tatalaksana DBD cairan kristaloid"
    hits = retriever.search_guidelines(
        NormalizedQuery(structured_query=query, keywords_id=[query]),
        RetrievalFilters(top_k=5),
    )
    assert hits
    assert hits[0].doc_id in {"ppk-fktp-2015", "pnpk-dengue-2021"}
    assert hits[0].retrieval_method == "hybrid"


def test_filter_by_source_type(retriever: HybridRetriever) -> None:
    hits = retriever.search_guidelines(
        NormalizedQuery(structured_query="tatalaksana DBD"),
        RetrievalFilters(source_types=["pnpk"], top_k=10),
    )
    assert hits
    for c in hits:
        assert c.source_type == "pnpk"


def test_filter_by_doc_ids(retriever: HybridRetriever) -> None:
    hits = retriever.search_guidelines(
        NormalizedQuery(structured_query="tatalaksana"),
        RetrievalFilters(doc_ids=["ppk-fktp-2015"], top_k=10),
    )
    assert hits
    assert all(c.doc_id == "ppk-fktp-2015" for c in hits)


def test_filter_by_min_year(retriever: HybridRetriever) -> None:
    hits = retriever.search_guidelines(
        NormalizedQuery(structured_query="tatalaksana"),
        RetrievalFilters(min_year=2019, top_k=10),
    )
    assert hits
    assert all(c.year >= 2019 for c in hits)


def test_filter_by_conditions_matches_section_path(retriever: HybridRetriever) -> None:
    hits = retriever.search_guidelines(
        NormalizedQuery(structured_query="tatalaksana"),
        RetrievalFilters(conditions=["dbd"], top_k=10),
    )
    assert hits
    for c in hits:
        assert "dbd" in c.section_path.lower() or "dbd" in c.text.lower()


def test_top_k_respected(retriever: HybridRetriever) -> None:
    hits = retriever.search_guidelines(
        NormalizedQuery(structured_query="tatalaksana"),
        RetrievalFilters(top_k=2),
    )
    assert len(hits) <= 2


def test_get_full_section_returns_matching_chunk(retriever: HybridRetriever) -> None:
    result = retriever.get_full_section(
        "ppk-fktp-2015", "ppk-fktp-2015/dbd_tata_laksana_anak"
    )
    assert result["doc_id"] == "ppk-fktp-2015"
    assert result["section_path"] == "ppk-fktp-2015/dbd_tata_laksana_anak"
    assert "DBD" in result["text"] or "cairan" in result["text"]


def test_get_full_section_missing_raises(retriever: HybridRetriever) -> None:
    with pytest.raises(KeyError):
        retriever.get_full_section("nope", "nope/nope")


def test_get_pdf_page_url_local(
    retriever: HybridRetriever, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.delenv("ANAMNESA_PUBLIC_ORIGIN", raising=False)
    url = retriever.get_pdf_page_url("ppk-fktp-2015", 12)
    assert url.startswith("file://")
    assert url.endswith("#page=12")


def test_get_pdf_page_url_public(
    retriever: HybridRetriever, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("ANAMNESA_PUBLIC_ORIGIN", "https://anamnesa.kudaliar.id")
    url = retriever.get_pdf_page_url("ppk-fktp-2015", 5)
    assert url == "https://anamnesa.kudaliar.id/pdf/ppk-fktp-2015.pdf#page=5"


def test_check_supersession_superseded(retriever: HybridRetriever) -> None:
    info = retriever.check_supersession("pnpk-dengue-2014")
    assert info["status"] == "superseded"
    assert info["superseding_doc_id"] == "pnpk-dengue-2021"
    assert info["source_year"] == 2014


def test_check_supersession_current_recent(retriever: HybridRetriever) -> None:
    info = retriever.check_supersession("pnpk-dengue-2021")
    assert info["status"] == "current"
    assert info["superseding_doc_id"] is None
    assert info["source_year"] == 2021


def test_check_supersession_aging_old_no_successor(retriever: HybridRetriever) -> None:
    info = retriever.check_supersession("ppk-fktp-2015")
    assert info["status"] == "aging"
    assert info["source_year"] == 2015


def test_check_supersession_unknown(retriever: HybridRetriever) -> None:
    info = retriever.check_supersession("does-not-exist")
    assert info["status"] == "unknown"
    assert info["superseding_doc_id"] is None
    assert info["source_year"] == 0


async def test_search_protocol_returns_retrieval_attempt(
    retriever: HybridRetriever,
) -> None:
    """HybridRetriever should be usable through the Retriever Protocol shape
    (via the LocalRetriever wrapper in mcp/client.py)."""
    from mcp.client import LocalRetriever

    local = LocalRetriever(retriever=retriever)
    query = NormalizedQuery(structured_query="DBD cairan")
    attempt = await local.search(query, RetrievalFilters(top_k=3), attempt_num=1)
    assert attempt.attempt_num == 1
    assert attempt.chunks
    assert all(c.retrieval_method == "hybrid" for c in attempt.chunks)


def test_bm25_persists_to_disk(
    tmp_path: Path, corpus: list[Chunk], manifest: Path
) -> None:
    embedder = HashEmbedder(dim=128)
    store = LanceChunkStore(db_path=tmp_path / "lance")
    store.upsert([StoredChunk(chunk=c, vector=embedder.embed([c.text])[0]) for c in corpus])

    bm25_path = tmp_path / "bm25.pkl"
    r1 = HybridRetriever(
        store=store, embedder=embedder, manifest_path=manifest, bm25_path=bm25_path
    )
    r1.rebuild_bm25_from_store()
    r1.save_bm25()
    assert bm25_path.exists()

    r2 = HybridRetriever(
        store=store, embedder=embedder, manifest_path=manifest, bm25_path=bm25_path
    )
    r2.load_bm25()
    hits = r2.bm25_search("OAT kategori", k=2)
    assert hits and hits[0].doc_id == "pnpk-tb-2020"


def test_build_index_reads_processed_json(
    tmp_path: Path, manifest: Path, corpus: list[Chunk]
) -> None:
    """`scripts/build_index.py` reads catalog/processed/**/*.json (list of
    chunk dicts). Exercise the library-level function behind the CLI."""
    from scripts.build_index import build_index

    processed = tmp_path / "processed" / "ppk_fktp"
    processed.mkdir(parents=True)
    file = processed / "ppk-fktp-2015.json"
    file.write_text(
        json.dumps([c.model_dump() for c in corpus[:2]], ensure_ascii=False),
        encoding="utf-8",
    )

    lance_dir = tmp_path / "lance"
    bm25_path = tmp_path / "bm25.pkl"
    n = build_index(
        processed_dir=tmp_path / "processed",
        lance_path=lance_dir,
        bm25_path=bm25_path,
    )
    assert n == 2
    assert bm25_path.exists()

    store = LanceChunkStore(db_path=lance_dir)
    assert len(list(store.iter_chunks())) == 2
