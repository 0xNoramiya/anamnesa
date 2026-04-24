"""File-locked manifest writer for parallel crawler sub-agents.

Why this exists: Day-2 corpus discovery dispatches one sub-agent per
source (Kemenkes PNPK, PPK FKTP, program pedoman, Fornas, ...). They all
want to append ManifestRecords to the same `catalog/manifest.json`. A
naive read-modify-write races and loses records.

Guarantees:
  - **Mutual exclusion** via `fcntl.LOCK_EX` on a sibling `.lock` file.
    No two processes ever hold the write section at once.
  - **Upsert** on `doc_id`: appending a record whose id already exists
    updates it in place rather than duplicating.
  - **Atomic replace**: serialization goes to a temp file in the same
    directory, then `os.replace` swaps it in. A crash mid-write cannot
    leave a half-written manifest.
  - **UTF-8, no ASCII escaping**: Bahasa titles round-trip verbatim.

CLI (used by crawler sub-agents via Bash):

    python -m tools.manifest_append \
        --manifest catalog/manifest.json \
        --record-json '{"doc_id": "pnpk-dengue-2020", ...}'
"""

from __future__ import annotations

import argparse
import fcntl
import json
import os
import sys
import tempfile
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Literal

import structlog

from core.manifest import Manifest, ManifestRecord

log = structlog.get_logger("anamnesa.tools.manifest_append")


@dataclass(frozen=True)
class AppendResult:
    doc_id: str
    action: Literal["inserted", "updated"]


@contextmanager
def _exclusive_lock(manifest_path: Path):  # type: ignore[no-untyped-def]
    """Hold an exclusive flock on a sibling lockfile for the duration."""
    manifest_path.parent.mkdir(parents=True, exist_ok=True)
    lock_path = manifest_path.with_name(manifest_path.name + ".lock")
    lock_path.touch(exist_ok=True)
    fd = os.open(str(lock_path), os.O_RDWR)
    try:
        fcntl.flock(fd, fcntl.LOCK_EX)
        yield
    finally:
        try:
            fcntl.flock(fd, fcntl.LOCK_UN)
        finally:
            os.close(fd)


def _load_or_init(manifest_path: Path) -> Manifest:
    if not manifest_path.exists():
        return Manifest()
    raw = manifest_path.read_text(encoding="utf-8")
    if not raw.strip():
        return Manifest()
    return Manifest.model_validate_json(raw)


def _atomic_write(manifest_path: Path, manifest: Manifest) -> None:
    """Serialize to a temp file in the same dir, then `os.replace` into place."""
    manifest_path.parent.mkdir(parents=True, exist_ok=True)
    payload = manifest.model_dump(mode="json")
    tmp_fd, tmp_name = tempfile.mkstemp(
        prefix=".manifest-", suffix=".json.tmp", dir=str(manifest_path.parent)
    )
    try:
        with os.fdopen(tmp_fd, "w", encoding="utf-8") as f:
            json.dump(payload, f, indent=2, ensure_ascii=False)
            f.flush()
            os.fsync(f.fileno())
        os.replace(tmp_name, manifest_path)
    except BaseException:
        # Remove the temp file on any failure before rename so we don't leak
        # a half-written artifact in the manifest directory.
        if os.path.exists(tmp_name):
            try:
                os.unlink(tmp_name)
            except OSError:
                pass
        raise


def append_record(record: ManifestRecord, manifest_path: Path) -> AppendResult:
    """Append `record` to `manifest_path`, upserting by `doc_id`."""
    with _exclusive_lock(manifest_path):
        manifest = _load_or_init(manifest_path)
        idx = manifest.index_by_id().get(record.doc_id)
        if idx is None:
            manifest.documents.append(record)
            action: Literal["inserted", "updated"] = "inserted"
        else:
            manifest.documents[idx] = record
            action = "updated"
        manifest.generated_at = datetime.now(UTC)
        _atomic_write(manifest_path, manifest)
        log.info(
            "manifest_append",
            doc_id=record.doc_id,
            action=action,
            manifest=str(manifest_path),
            total=len(manifest.documents),
        )
        return AppendResult(doc_id=record.doc_id, action=action)


def _cli(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="python -m tools.manifest_append",
        description="Append a ManifestRecord to catalog/manifest.json (file-locked).",
    )
    parser.add_argument(
        "--manifest",
        default="catalog/manifest.json",
        help="Path to manifest.json (default: catalog/manifest.json)",
    )
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument(
        "--record-json",
        help="JSON string of a ManifestRecord.",
    )
    group.add_argument(
        "--record-file",
        help="Path to a JSON file containing a ManifestRecord.",
    )
    args = parser.parse_args(argv)

    raw = args.record_json if args.record_json is not None else Path(args.record_file).read_text(
        encoding="utf-8"
    )
    record = ManifestRecord.model_validate_json(raw)
    result = append_record(record, Path(args.manifest))
    print(json.dumps({"doc_id": result.doc_id, "action": result.action}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    sys.exit(_cli())
