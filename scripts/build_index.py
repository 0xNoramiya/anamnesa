"""Build the Anamnesa retrieval index from `catalog/processed/**/*.json`.

Each processed JSON file is a list of Chunk-shaped dicts (matching
`core.state.Chunk`). This CLI:

  1. Loads every chunk from `processed_dir`.
  2. Embeds them with a `HashEmbedder` (dev default — swap for BGE later).
  3. Upserts them into the LanceDB chunk store at `lance_path`.
  4. Rebuilds the BM25 sidecar and pickles it to `bm25_path`.

Env defaults:
    LANCE_DB_PATH     (default ./index/lance)
    BM25_INDEX_PATH   (default ./index/bm25.pkl)
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

import structlog

from core.chunk_store import LanceChunkStore, StoredChunk
from core.embeddings import Embedder, HashEmbedder
from core.retrieval import DEFAULT_BM25_PATH, HybridRetriever
from core.state import Chunk

log = structlog.get_logger("anamnesa.retrieval")


def _iter_chunk_files(processed_dir: Path) -> list[Path]:
    if not processed_dir.exists():
        return []
    return sorted(processed_dir.rglob("*.json"))


def _load_chunks(path: Path) -> list[Chunk]:
    with path.open("r", encoding="utf-8") as fh:
        payload = json.load(fh)
    if not isinstance(payload, list):
        raise ValueError(f"{path}: expected a list of chunk dicts")
    return [Chunk.model_validate(item) for item in payload]


def build_index(
    *,
    processed_dir: Path,
    lance_path: Path,
    bm25_path: Path,
    embedder: Embedder | None = None,
) -> int:
    """Build/refresh the retrieval index. Returns the number of chunks indexed."""
    emb = embedder or HashEmbedder()

    files = _iter_chunk_files(processed_dir)
    log.info("build_index.discover", files=len(files), root=str(processed_dir))

    all_chunks: list[Chunk] = []
    for f in files:
        chunks = _load_chunks(f)
        all_chunks.extend(chunks)
        log.info("build_index.file_loaded", path=str(f), chunks=len(chunks))

    store = LanceChunkStore(db_path=lance_path)

    if all_chunks:
        vectors = emb.embed([c.text for c in all_chunks])
        stored = [
            StoredChunk(chunk=c, vector=vec)
            for c, vec in zip(all_chunks, vectors, strict=True)
        ]
        store.upsert(stored)

    r = HybridRetriever(
        store=store,
        embedder=emb,
        bm25_path=bm25_path,
    )
    r.rebuild_bm25_from_store()
    r.save_bm25()

    log.info(
        "build_index.done",
        chunks=len(all_chunks),
        lance=str(lance_path),
        bm25=str(bm25_path),
    )
    return len(all_chunks)


def _default_lance_path() -> Path:
    env = os.environ.get("LANCE_DB_PATH")
    return Path(env) if env else Path("./index/lance")


def _default_bm25_path() -> Path:
    env = os.environ.get("BM25_INDEX_PATH")
    return Path(env) if env else DEFAULT_BM25_PATH


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Build Anamnesa retrieval index.")
    parser.add_argument(
        "--processed-dir",
        type=Path,
        default=Path("./catalog/processed"),
        help="Root of processed chunk JSON (list of Chunk dicts per file).",
    )
    parser.add_argument(
        "--lance-path",
        type=Path,
        default=_default_lance_path(),
        help="LanceDB directory (default $LANCE_DB_PATH or ./index/lance).",
    )
    parser.add_argument(
        "--bm25-path",
        type=Path,
        default=_default_bm25_path(),
        help="BM25 pickle path (default $BM25_INDEX_PATH or ./index/bm25.pkl).",
    )
    args = parser.parse_args(argv)

    n = build_index(
        processed_dir=args.processed_dir,
        lance_path=args.lance_path,
        bm25_path=args.bm25_path,
    )
    log.info("build_index.cli_done", chunks=n)
    return 0


if __name__ == "__main__":
    sys.exit(main())
