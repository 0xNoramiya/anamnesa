"""Pluggable embedder interface for Anamnesa retrieval.

Two concrete embedders live here:

  - `HashEmbedder` — deterministic, dep-free, semantically useless but
    dimensionally consistent. Used for tests and as a plumbing default.
  - `BGEEmbedder`  — real multilingual embedder backed by
    `sentence-transformers/BAAI/bge-m3` (1024-dim). Lazy-loads the model
    on first `embed()` call; raises `EmbedderUnavailableError` with an
    install hint if `sentence-transformers` isn't installed.

Swap is driven by `scripts/reindex.py --embedder bge-m3`.
"""

from __future__ import annotations

import hashlib
import os
import re
import sys
from typing import TYPE_CHECKING, Any, Protocol, runtime_checkable

import structlog

if TYPE_CHECKING:
    from sentence_transformers import SentenceTransformer

log = structlog.get_logger("anamnesa.retrieval")

_TOKEN_RE = re.compile(r"[A-Za-z0-9\u00C0-\u024F]+", re.UNICODE)


@runtime_checkable
class Embedder(Protocol):
    """Dense embedding interface used by the retrieval layer."""

    @property
    def dim(self) -> int: ...

    def embed(self, texts: list[str]) -> list[list[float]]: ...


def _tokenize(text: str) -> list[str]:
    return [tok.lower() for tok in _TOKEN_RE.findall(text)]


class HashEmbedder:
    """Deterministic bag-of-hashed-tokens embedder.

    Each token is hashed into a bucket of the final vector; bucket weights are
    accumulated then L2-normalized. Shared tokens cluster inputs together, so
    exact-match queries land on the right chunk even though the embedder does
    not understand meaning. Suitable ONLY for dev and tests.
    """

    def __init__(self, dim: int = 256) -> None:
        if dim < 8:
            raise ValueError("HashEmbedder dim must be >= 8")
        self._dim = dim

    @property
    def dim(self) -> int:
        return self._dim

    def embed(self, texts: list[str]) -> list[list[float]]:
        return [self._embed_one(t) for t in texts]

    def _embed_one(self, text: str) -> list[float]:
        vec = [0.0] * self._dim
        tokens = _tokenize(text)
        if not tokens:
            # Unit vector on dim 0 so empty texts do not produce NaN on norm.
            vec[0] = 1.0
            return vec
        for tok in tokens:
            h = hashlib.blake2b(tok.encode("utf-8"), digest_size=8).digest()
            bucket = int.from_bytes(h[:4], "big") % self._dim
            # Deterministic sign so different tokens don't cancel each other
            # as aggressively as pure positive counts would.
            sign = 1.0 if h[4] & 0x01 else -1.0
            vec[bucket] += sign
        norm = sum(v * v for v in vec) ** 0.5
        if norm == 0.0:
            vec[0] = 1.0
            return vec
        return [v / norm for v in vec]


class EmbedderUnavailableError(RuntimeError):
    """Raised when a backend dependency (e.g. sentence-transformers) is missing."""


BGE_M3_DIMENSION = 1024


def _load_sentence_transformer_cls() -> type[SentenceTransformer]:
    """Import SentenceTransformer lazily so torch isn't pulled at module import."""
    try:
        from sentence_transformers import SentenceTransformer
    except ImportError as exc:
        raise EmbedderUnavailableError(
            "sentence-transformers is not installed. Install with:\n"
            "    uv pip install -e '.[embeddings]'\n"
            "(or `pip install -e '.[embeddings]'`). This pulls torch and "
            "~2GB of BGE-M3 weights on first use."
        ) from exc
    return SentenceTransformer


def _detect_device() -> str:
    """Pick CUDA → MPS → CPU, conservatively. Torch must be loaded to probe."""
    try:
        import torch
    except ImportError:
        return "cpu"
    if torch.cuda.is_available():
        return "cuda"
    if getattr(torch.backends, "mps", None) is not None and torch.backends.mps.is_available():
        return "mps"
    return "cpu"


class BGEEmbedder:
    """Real multilingual embedder — `BAAI/bge-m3` (1024-dim).

    Lazy: construction does not load the model; the first `embed()` call does.
    Use `embed_queries()` for queries — BGE-M3 recommends a `"query: "` prefix
    that shouldn't be applied to ingested documents.
    """

    DEFAULT_MODEL_ID = "BAAI/bge-m3"
    DEFAULT_BATCH_SIZE = 32
    # BGE-M3 supports up to 8192 tokens but attention is O(seq^2), and batches
    # pad to the longest input. PPK FKTP has 60K-char sections; capping at 1024
    # keeps the clinical signal (condition, drug, dose concentrate near headers)
    # and yields a ~30-60x speedup.
    DEFAULT_MAX_SEQ_LENGTH = 1024
    QUERY_PREFIX = "query: "

    def __init__(
        self,
        *,
        model_id: str | None = None,
        batch_size: int = DEFAULT_BATCH_SIZE,
        device: str | None = None,
        max_seq_length: int | None = DEFAULT_MAX_SEQ_LENGTH,
    ) -> None:
        self.model_id = model_id or os.getenv("BGE_M3_MODEL", self.DEFAULT_MODEL_ID)
        self.batch_size = batch_size
        self.max_seq_length = max_seq_length
        self._explicit_device = device
        self._model: SentenceTransformer | None = None
        self._device_cached: str | None = None

    @property
    def dim(self) -> int:
        # Hard-coded so reading `dim` does not force model load.
        return BGE_M3_DIMENSION

    @property
    def device(self) -> str:
        if self._device_cached is not None:
            return self._device_cached
        if self._explicit_device is not None:
            self._device_cached = self._explicit_device
        else:
            self._device_cached = _detect_device()
        return self._device_cached

    def _ensure_loaded(self) -> SentenceTransformer:
        if self._model is not None:
            return self._model
        cls = _load_sentence_transformer_cls()
        log.info("bge.loading", model=self.model_id, device=self.device)
        model = cls(self.model_id, device=self.device)
        if self.max_seq_length is not None:
            model.max_seq_length = self.max_seq_length
        self._model = model
        log.info(
            "bge.loaded",
            model=self.model_id,
            device=self.device,
            max_seq_length=self.max_seq_length,
        )
        return self._model

    def embed(self, texts: list[str]) -> list[list[float]]:
        return self._encode(texts)

    def embed_queries(self, texts: list[str]) -> list[list[float]]:
        """Embed query-mode texts (prepends the BGE-M3 `"query: "` prefix)."""
        prefixed = [f"{self.QUERY_PREFIX}{t}" for t in texts]
        return self._encode(prefixed)

    def _encode(self, texts: list[str]) -> list[list[float]]:
        model = self._ensure_loaded()
        vectors = model.encode(
            texts,
            batch_size=self.batch_size,
            normalize_embeddings=True,
            show_progress_bar=False,
            convert_to_numpy=True,
        )
        return [row.tolist() for row in vectors]


def build_embedder(name: str, **kwargs: Any) -> Embedder:
    """Factory used by `scripts/reindex.py`. Names: `hash`, `bge-m3`."""
    name = name.lower()
    if name in {"hash", "hash-embedder", "hashembedder"}:
        return HashEmbedder(**kwargs)
    if name in {"bge", "bge-m3", "bgeembedder"}:
        return BGEEmbedder(**kwargs)
    raise ValueError(
        f"Unknown embedder name: {name!r}. Known: 'hash', 'bge-m3'."
    )


if __name__ == "__main__":
    which = sys.argv[1] if len(sys.argv) > 1 else "hash"
    e = build_embedder(which)
    out = e.embed(["hello world"])
    print(f"{type(e).__name__} dim={e.dim} shape=[{len(out)}, {len(out[0])}]")
