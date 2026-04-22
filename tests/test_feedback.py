"""Tests for the thumbs up/down feedback store."""

from __future__ import annotations

from pathlib import Path

import pytest

from core.feedback import FeedbackStore


def test_add_and_stats_roundtrip(tmp_path: Path) -> None:
    store = FeedbackStore(tmp_path / "fb.db")
    a = store.add(query_id="Q1", query_text="DBD anak", rating="up")
    b = store.add(query_id="Q2", query_text="TB paru", rating="down", note="kurang lengkap")
    assert a != b
    s = store.stats()
    assert s["total"] == 2
    assert s["up"] == 1
    assert s["down"] == 1
    assert len(s["recent"]) == 2
    notes = [r["note"] for r in s["recent"]]
    assert "kurang lengkap" in notes


def test_invalid_rating_rejected(tmp_path: Path) -> None:
    store = FeedbackStore(tmp_path / "fb.db")
    with pytest.raises(ValueError):
        store.add(query_id="Q1", query_text="foo", rating="meh")


def test_note_is_truncated(tmp_path: Path) -> None:
    store = FeedbackStore(tmp_path / "fb.db")
    long_note = "x" * 3000
    store.add(query_id="Q1", query_text="foo", rating="down", note=long_note)
    s = store.stats()
    assert len(s["recent"][0]["note"]) == 2000


def test_query_text_is_truncated(tmp_path: Path) -> None:
    store = FeedbackStore(tmp_path / "fb.db")
    long_q = "y" * 3000
    store.add(query_id="Q1", query_text=long_q, rating="up")
    s = store.stats()
    assert len(s["recent"][0]["query_text"]) == 2000


def test_empty_note_stored_as_null(tmp_path: Path) -> None:
    store = FeedbackStore(tmp_path / "fb.db")
    store.add(query_id="Q1", query_text="foo", rating="up", note="")
    s = store.stats()
    assert s["recent"][0]["note"] is None


def test_many_entries_recent_capped_at_20(tmp_path: Path) -> None:
    store = FeedbackStore(tmp_path / "fb.db")
    for i in range(30):
        store.add(query_id=f"Q{i}", query_text=f"q-{i}", rating="up")
    s = store.stats()
    assert s["total"] == 30
    assert len(s["recent"]) == 20


def test_smoke_entries_filtered_by_default(tmp_path: Path) -> None:
    """Prod smoke-test writes rows with query_id='SMOKE-...'. Default
    stats should hide them so /admin/feedback shows only real signal."""
    store = FeedbackStore(tmp_path / "fb.db")
    store.add(query_id="Q1", query_text="real query", rating="up")
    store.add(query_id="Q2", query_text="another real", rating="down")
    store.add(query_id="SMOKE-12345", query_text="prod smoke-test ping", rating="up")
    store.add(query_id="SMOKE-67890", query_text="prod smoke-test ping", rating="down")

    default = store.stats()
    assert default["total"] == 2
    assert default["up"] == 1
    assert default["down"] == 1
    assert all(r["query_text"] != "prod smoke-test ping" for r in default["recent"])

    with_smoke = store.stats(include_smoke=True)
    assert with_smoke["total"] == 4
    assert with_smoke["up"] == 2
    assert with_smoke["down"] == 2
