"""Tests for the embedder module.

The real `BAAI/bge-m3` weights are ~2GB and pull torch. These tests use
monkeypatching to avoid loading either — we assert on the construction
seam (`_load_sentence_transformer_cls`) and the call shape.
"""

from __future__ import annotations

from typing import Any

import pytest

from core import embeddings as emb_mod
from core.embeddings import (
    BGE_M3_DIMENSION,
    BGEEmbedder,
    EmbedderUnavailableError,
    HashEmbedder,
    build_embedder,
)


def test_hash_embedder_returns_normalized_vector_of_configured_dim() -> None:
    e = HashEmbedder(dim=64)
    [vec] = e.embed(["halo dunia"])
    assert len(vec) == 64
    norm = sum(v * v for v in vec) ** 0.5
    assert abs(norm - 1.0) < 1e-6


def test_hash_embedder_deterministic_across_calls() -> None:
    e = HashEmbedder(dim=32)
    a = e.embed(["DBD anak derajat 2"])[0]
    b = e.embed(["DBD anak derajat 2"])[0]
    assert a == b


class _FakeSentenceTransformer:
    """Minimal stand-in for `sentence_transformers.SentenceTransformer`."""

    def __init__(self, model_id: str, *, device: str) -> None:
        self.model_id = model_id
        self.device = device
        self.encode_calls: list[dict[str, Any]] = []

    def encode(
        self,
        texts: list[str],
        *,
        batch_size: int,
        normalize_embeddings: bool,
        show_progress_bar: bool,
        convert_to_numpy: bool,
    ) -> Any:
        import numpy as np  # numpy is a transitive install, available.

        self.encode_calls.append(
            {
                "texts": list(texts),
                "batch_size": batch_size,
                "normalize_embeddings": normalize_embeddings,
                "show_progress_bar": show_progress_bar,
                "convert_to_numpy": convert_to_numpy,
            }
        )
        # Return a (N, 1024) array of deterministic floats so callers can
        # see distinct vectors per input.
        return np.array(
            [[float((hash(t) + i) % 17) / 17.0 for i in range(BGE_M3_DIMENSION)] for t in texts],
            dtype="float32",
        )


def _install_fake_st(monkeypatch: pytest.MonkeyPatch) -> type[_FakeSentenceTransformer]:
    """Monkeypatch the loader seam to return our fake class."""
    monkeypatch.setattr(
        emb_mod,
        "_load_sentence_transformer_cls",
        lambda: _FakeSentenceTransformer,
    )
    # Also stub device detection to keep tests hermetic.
    monkeypatch.setattr(emb_mod, "_detect_device", lambda: "cpu")
    return _FakeSentenceTransformer


def test_bge_embedder_construction_is_cheap_and_does_not_load() -> None:
    """Constructor must not touch the model — `_model` stays None."""
    e = BGEEmbedder()
    assert e._model is None
    # dim must be readable without triggering load
    assert e.dim == BGE_M3_DIMENSION
    assert e._model is None


def test_bge_embedder_lazy_loads_on_first_embed(monkeypatch: pytest.MonkeyPatch) -> None:
    _install_fake_st(monkeypatch)
    e = BGEEmbedder()
    assert e._model is None
    e.embed(["sepsis dewasa"])
    assert e._model is not None  # loaded exactly once on first call


def test_bge_embedder_embed_shape(monkeypatch: pytest.MonkeyPatch) -> None:
    _install_fake_st(monkeypatch)
    e = BGEEmbedder()
    vectors = e.embed(["a", "b", "c"])
    assert isinstance(vectors, list)
    assert len(vectors) == 3
    assert all(isinstance(v, list) for v in vectors)
    assert all(len(v) == BGE_M3_DIMENSION for v in vectors)


def test_bge_embedder_embed_does_not_prepend_query_prefix(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _install_fake_st(monkeypatch)
    e = BGEEmbedder()
    e.embed(["dengue"])
    assert e._model is not None
    call = e._model.encode_calls[-1]
    assert call["texts"] == ["dengue"]


def test_bge_embedder_embed_queries_prepends_query_prefix(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _install_fake_st(monkeypatch)
    e = BGEEmbedder()
    e.embed_queries(["dengue"])
    assert e._model is not None
    call = e._model.encode_calls[-1]
    assert call["texts"] == ["query: dengue"]


def test_bge_embedder_honors_batch_size(monkeypatch: pytest.MonkeyPatch) -> None:
    _install_fake_st(monkeypatch)
    e = BGEEmbedder(batch_size=17)
    e.embed(["a"])
    assert e._model is not None
    assert e._model.encode_calls[-1]["batch_size"] == 17


def test_bge_embedder_normalize_embeddings_is_true(monkeypatch: pytest.MonkeyPatch) -> None:
    _install_fake_st(monkeypatch)
    e = BGEEmbedder()
    e.embed(["x"])
    assert e._model is not None
    assert e._model.encode_calls[-1]["normalize_embeddings"] is True


def test_bge_embedder_missing_dep_raises_with_install_hint(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def _raise() -> Any:
        raise EmbedderUnavailableError(
            "sentence-transformers is not installed. Install with:\n"
            "    uv pip install -e '.[embeddings]'\n"
        )

    monkeypatch.setattr(emb_mod, "_load_sentence_transformer_cls", _raise)
    e = BGEEmbedder()
    with pytest.raises(EmbedderUnavailableError) as excinfo:
        e.embed(["x"])
    msg = str(excinfo.value)
    assert "pip install" in msg
    assert "[embeddings]" in msg


def test_bge_embedder_dim_is_1024_without_load() -> None:
    e = BGEEmbedder()
    assert e.dim == 1024
    assert e._model is None  # dim access must not trigger load


def test_build_embedder_hash() -> None:
    e = build_embedder("hash")
    assert isinstance(e, HashEmbedder)


def test_build_embedder_bge() -> None:
    e = build_embedder("bge-m3")
    assert isinstance(e, BGEEmbedder)


def test_build_embedder_unknown_raises() -> None:
    with pytest.raises(ValueError, match="Unknown embedder name"):
        build_embedder("openai-ada-002")
