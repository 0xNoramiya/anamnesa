"""Drop-and-rebuild the Anamnesa retrieval index with a chosen embedder.

This is the from-scratch sibling of `scripts/build_index.py`. Use it when
you want to swap embedders (e.g. `hash` → `bge-m3`) or recover from a
corrupted index.

Usage:
    python -m scripts.reindex --embedder bge-m3             # real multilingual
    python -m scripts.reindex --embedder hash               # dev stub
    python -m scripts.reindex --batch-size 16 --yes         # skip prompt
    python -m scripts.reindex --dry-run                     # show plan, no writes

The real `bge-m3` path requires `uv pip install -e '.[embeddings]'` and
downloads ~2GB of model weights on first use.
"""

from __future__ import annotations

import argparse
import os
import shutil
import sys
from pathlib import Path

import structlog

from core.chunk_store import LanceChunkStore, StoredChunk
from core.embeddings import Embedder, build_embedder
from core.retrieval import DEFAULT_BM25_PATH, HybridRetriever
from core.state import Chunk
from scripts.build_index import _iter_chunk_files, _load_chunks

log = structlog.get_logger("anamnesa.reindex")


def _default_lance_path() -> Path:
    env = os.environ.get("LANCE_DB_PATH")
    return Path(env) if env else Path("./index/lance")


def _default_bm25_path() -> Path:
    env = os.environ.get("BM25_INDEX_PATH")
    return Path(env) if env else DEFAULT_BM25_PATH


def _confirm(msg: str, *, assume_yes: bool) -> bool:
    if assume_yes:
        return True
    if not sys.stdin.isatty():
        # Non-interactive: refuse destructive op unless --yes was passed.
        print(f"non-interactive — pass --yes to proceed: {msg}", file=sys.stderr)
        return False
    resp = input(f"{msg} [y/N]: ").strip().lower()
    return resp in {"y", "yes"}


def _embed_in_batches(
    embedder: Embedder,
    texts: list[str],
    *,
    batch_size: int,
) -> list[list[float]]:
    """Embed a long list in batches so we don't OOM on a single call.

    Some embedders (like `sentence-transformers`) internally batch, but
    we batch at this layer too so progress is observable and a crash
    mid-way leaves some rows processed rather than none.
    """
    out: list[list[float]] = []
    total = len(texts)
    i = 0
    while i < total:
        end = min(i + batch_size, total)
        out.extend(embedder.embed(texts[i:end]))
        i = end
        if i % (batch_size * 4) == 0 or i == total:
            log.info("reindex.embed_progress", done=i, total=total)
    return out


def reindex(
    *,
    processed_dir: Path,
    lance_path: Path,
    bm25_path: Path,
    embedder_name: str,
    batch_size: int,
    dry_run: bool,
    assume_yes: bool,
) -> int:
    """Drop LanceDB, rebuild with fresh embeddings. Returns chunk count.

    Returns -1 on user-declined confirmation (not a failure; nothing was
    touched).
    """
    files = _iter_chunk_files(processed_dir)
    if not files:
        log.warning("reindex.no_files", dir=str(processed_dir))
        return 0

    all_chunks: list[Chunk] = []
    for f in files:
        all_chunks.extend(_load_chunks(f))
    log.info(
        "reindex.plan",
        files=len(files),
        chunks=len(all_chunks),
        embedder=embedder_name,
        lance=str(lance_path),
        bm25=str(bm25_path),
        batch_size=batch_size,
        dry_run=dry_run,
    )

    if dry_run:
        print(
            f"DRY RUN: would reindex {len(all_chunks)} chunks from "
            f"{len(files)} files using embedder={embedder_name!r}; "
            f"LanceDB path={lance_path}; BM25 path={bm25_path}."
        )
        return len(all_chunks)

    if not _confirm(
        f"This will DELETE the LanceDB index at {lance_path} and "
        f"rebuild from {len(all_chunks)} chunks. Continue?",
        assume_yes=assume_yes,
    ):
        log.info("reindex.declined")
        return -1

    # 1. Drop the existing LanceDB directory so the new embedder's dim wins.
    if lance_path.exists():
        log.info("reindex.dropping_lance", path=str(lance_path))
        shutil.rmtree(lance_path)

    # 2. Build embedder. This is where `bge-m3` triggers the ~2GB download
    #    on first invocation; `hash` is free.
    try:
        embedder = build_embedder(embedder_name)
    except Exception as exc:
        log.exception("reindex.embedder_build_failed", embedder=embedder_name)
        print(f"Failed to build embedder {embedder_name!r}: {exc}", file=sys.stderr)
        return 1

    # 3. Embed all chunks in batches.
    try:
        vectors = _embed_in_batches(
            embedder, [c.text for c in all_chunks], batch_size=batch_size
        )
    except Exception as exc:  # pragma: no cover — CLI ergonomics
        msg = str(exc).lower()
        if "out of memory" in msg or "cuda" in msg:
            print(
                "OOM while embedding. Try a smaller --batch-size "
                "(e.g. 8 or 4).",
                file=sys.stderr,
            )
        raise

    # 4. Upsert into a fresh LanceChunkStore.
    store = LanceChunkStore(db_path=lance_path)
    stored = [
        StoredChunk(chunk=c, vector=vec)
        for c, vec in zip(all_chunks, vectors, strict=True)
    ]
    store.upsert(stored)

    # 5. Rebuild BM25 sidecar.
    r = HybridRetriever(store=store, embedder=embedder, bm25_path=bm25_path)
    r.rebuild_bm25_from_store()
    r.save_bm25()

    log.info(
        "reindex.done",
        chunks=len(all_chunks),
        embedder=embedder_name,
        lance=str(lance_path),
        bm25=str(bm25_path),
    )
    return len(all_chunks)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="python -m scripts.reindex",
        description=(
            "Drop and rebuild the Anamnesa retrieval index with a chosen embedder. "
            "Use this when swapping embedders (e.g. hash → bge-m3)."
        ),
    )
    parser.add_argument(
        "--embedder", choices=["hash", "bge-m3"], default="hash",
        help="Which embedder to use. Default: hash.",
    )
    parser.add_argument(
        "--processed-dir", type=Path, default=Path("./catalog/processed"),
    )
    parser.add_argument("--lance-path", type=Path, default=_default_lance_path())
    parser.add_argument("--bm25-path", type=Path, default=_default_bm25_path())
    parser.add_argument("--batch-size", type=int, default=32)
    parser.add_argument(
        "--yes", action="store_true",
        help="Skip the confirmation prompt. Required for non-interactive use.",
    )
    parser.add_argument(
        "--dry-run", action="store_true",
        help="Print the plan and exit without touching the index.",
    )
    args = parser.parse_args(argv)

    n = reindex(
        processed_dir=args.processed_dir,
        lance_path=args.lance_path,
        bm25_path=args.bm25_path,
        embedder_name=args.embedder,
        batch_size=args.batch_size,
        dry_run=args.dry_run,
        assume_yes=args.yes,
    )
    if n < 0:
        return 2  # user declined
    return 0


if __name__ == "__main__":
    sys.exit(main())
