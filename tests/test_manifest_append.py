"""Tests for `tools.manifest_append` — file-locked manifest writer.

Correctness requirements (per CLAUDE.md repo layout notes):
- Race-free under parallel appends from sub-agents.
- Upsert semantics: appending a record whose `doc_id` already exists
  updates that record rather than duplicating.
- Atomic: a crash mid-write never leaves a half-written manifest.
"""

from __future__ import annotations

import json
import multiprocessing as mp
import os
from pathlib import Path

import pytest

from core.manifest import Manifest, ManifestRecord
from tools.manifest_append import AppendResult, append_record


def _record(doc_id: str, **overrides: object) -> ManifestRecord:
    base: dict[str, object] = {
        "doc_id": doc_id,
        "source_type": "pnpk",
        "title": f"Title for {doc_id}",
        "year": 2020,
        "source_url": f"https://example.test/{doc_id}.pdf",
        "discovered_by": "test",
    }
    base.update(overrides)
    return ManifestRecord.model_validate(base)


def test_missing_file_is_created_on_first_append(tmp_path: Path) -> None:
    manifest_path = tmp_path / "manifest.json"
    assert not manifest_path.exists()

    result = append_record(_record("pnpk-dengue-2020"), manifest_path)

    assert result.action == "inserted"
    assert manifest_path.exists()
    loaded = Manifest.model_validate_json(manifest_path.read_text(encoding="utf-8"))
    assert [d.doc_id for d in loaded.documents] == ["pnpk-dengue-2020"]


def test_two_distinct_records_both_appear(tmp_path: Path) -> None:
    manifest_path = tmp_path / "manifest.json"
    append_record(_record("pnpk-dengue-2020"), manifest_path)
    append_record(_record("pnpk-tb-2019"), manifest_path)

    loaded = Manifest.model_validate_json(manifest_path.read_text(encoding="utf-8"))
    assert sorted(d.doc_id for d in loaded.documents) == ["pnpk-dengue-2020", "pnpk-tb-2019"]


def test_duplicate_doc_id_upserts_rather_than_duplicates(tmp_path: Path) -> None:
    manifest_path = tmp_path / "manifest.json"
    append_record(_record("pnpk-dengue-2020", notes="first"), manifest_path)

    result = append_record(_record("pnpk-dengue-2020", notes="second"), manifest_path)

    assert result.action == "updated"
    loaded = Manifest.model_validate_json(manifest_path.read_text(encoding="utf-8"))
    assert len(loaded.documents) == 1
    assert loaded.documents[0].notes == "second"


def test_write_is_atomic_even_on_mid_write_interrupt(tmp_path: Path, monkeypatch) -> None:
    """Simulate failure between serialization and rename. The existing
    manifest must remain intact."""
    manifest_path = tmp_path / "manifest.json"
    append_record(_record("pnpk-dengue-2020"), manifest_path)
    original_bytes = manifest_path.read_bytes()

    from tools import manifest_append as mod

    def boom(*_args: object, **_kwargs: object) -> None:
        raise RuntimeError("simulated crash mid-rename")

    monkeypatch.setattr(mod.os, "replace", boom)

    with pytest.raises(RuntimeError, match="simulated crash"):
        append_record(_record("pnpk-tb-2019"), manifest_path)

    # The manifest must still parse and must still contain only the original doc.
    assert manifest_path.read_bytes() == original_bytes
    loaded = Manifest.model_validate_json(manifest_path.read_text(encoding="utf-8"))
    assert [d.doc_id for d in loaded.documents] == ["pnpk-dengue-2020"]

    # And no stray temp file should leak in the manifest's directory.
    allowed = {"manifest.json", "manifest.json.lock"}
    leftover = [p for p in manifest_path.parent.iterdir() if p.name not in allowed]
    assert leftover == [], f"unexpected leftover files: {leftover}"


def _append_worker(args: tuple[str, str]) -> AppendResult:
    from tools.manifest_append import append_record as ar  # reimport in subprocess

    path_str, doc_id = args
    return ar(_record(doc_id), Path(path_str))


def test_parallel_appends_preserve_every_record(tmp_path: Path) -> None:
    manifest_path = tmp_path / "manifest.json"
    n = 16
    doc_ids = [f"pnpk-doc-{i:02d}" for i in range(n)]

    # Use spawn context for clean child imports. Pool to parallelize.
    ctx = mp.get_context("spawn")
    with ctx.Pool(processes=4) as pool:
        results = pool.map(_append_worker, [(str(manifest_path), d) for d in doc_ids])

    assert {r.action for r in results} == {"inserted"}
    loaded = Manifest.model_validate_json(manifest_path.read_text(encoding="utf-8"))
    assert sorted(d.doc_id for d in loaded.documents) == sorted(doc_ids)


def test_bahasa_title_round_trips_without_ascii_escape(tmp_path: Path) -> None:
    manifest_path = tmp_path / "manifest.json"
    append_record(
        _record("pnpk-dbd-2020", title="Pedoman Nasional Pelayanan Kedokteran — DBD"),
        manifest_path,
    )
    raw = manifest_path.read_text(encoding="utf-8")
    # "—" is U+2014 EM DASH; ensure_ascii=False preserves it literally.
    assert "—" in raw
    assert "\\u2014" not in raw


def test_lockfile_is_sibling_and_does_not_appear_in_manifest(tmp_path: Path) -> None:
    manifest_path = tmp_path / "manifest.json"
    append_record(_record("pnpk-dengue-2020"), manifest_path)

    # Lockfile is allowed (convention: manifest.json.lock); no other junk.
    siblings = sorted(p.name for p in tmp_path.iterdir())
    assert siblings == ["manifest.json", "manifest.json.lock"] or siblings == ["manifest.json"]


def test_cli_json_input_appends_and_exits_zero(tmp_path: Path) -> None:
    import subprocess
    import sys

    manifest_path = tmp_path / "manifest.json"
    record = _record("pnpk-malaria-2017").model_dump(mode="json")

    env = os.environ.copy()
    env["PYTHONPATH"] = str(Path(__file__).resolve().parents[1])
    proc = subprocess.run(
        [
            sys.executable,
            "-m",
            "tools.manifest_append",
            "--manifest",
            str(manifest_path),
            "--record-json",
            json.dumps(record),
        ],
        capture_output=True,
        text=True,
        env=env,
        cwd=str(Path(__file__).resolve().parents[1]),
    )
    assert proc.returncode == 0, proc.stderr
    loaded = Manifest.model_validate_json(manifest_path.read_text(encoding="utf-8"))
    assert [d.doc_id for d in loaded.documents] == ["pnpk-malaria-2017"]
