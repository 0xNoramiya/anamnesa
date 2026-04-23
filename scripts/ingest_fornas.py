"""Fornas (Formularium Nasional) ingester.

Target: Kepmenkes HK.01.07/MENKES/2197/2023 — the current Fornas. ~300
pages of structured drug tables (kelas terapi → drug → forms/doses
→ peresepan maksimal + restriksi penggunaan).

Strategy: pdfplumber text extraction + one chunk per page. Fornas is
formatted as a regulatory document with the drug tables as the body,
so chunking by page preserves enough context for retrieval. More
sophisticated table-aware chunking is possible but out of scope for
this pass — per-page is enough to surface "which Fornas page talks
about paracetamol" on a keyword search.

Outputs:
  - catalog/processed/fornas/<doc_id>.json  (chunk list)
  - appended manifest record at catalog/manifest.json

Run on prod (where the PDF already is):
  .venv/bin/python -m scripts.ingest_fornas
"""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path
from typing import Any

import pdfplumber

# ---------------------------------------------------------------------------
# Config — specific to the 2023 Fornas. Swap these for the 2024 amendment
# if/when that ingest lands.
# ---------------------------------------------------------------------------
DOC_ID = "fornas-2023"
SOURCE_TYPE = "fornas"
TITLE = (
    "Formularium Nasional (Kepmenkes HK.01.07/MENKES/2197/2023)"
)
YEAR = 2023
AUTHORITY = "Kemenkes RI"
KEPMENKES = "HK.01.07/MENKES/2197/2023"
SOURCE_URL = (
    "https://farmalkes.kemkes.go.id/en/unduh/kepmenkes-2197-2023/"
)

REPO = Path(__file__).resolve().parents[1]
PDF_PATH = REPO / "catalog" / "cache" / "fornas" / "fornas-2023.pdf"
OUT_DIR = REPO / "catalog" / "processed" / "fornas"
MANIFEST_PATH = REPO / "catalog" / "manifest.json"


# ---------------------------------------------------------------------------
# Section-slug heuristic
# ---------------------------------------------------------------------------
# The Fornas pages open with a "KELAS TERAPI" header table on the first
# page where each kelas begins. Subsequent pages within the same kelas
# continue the drug list without repeating the class header. We carry
# the last-seen header forward so every chunk has a useful slug.

_CLASS_LINE = re.compile(
    r"\bkelas\s+terapi\s*[:.]?\s*(\d+)\.?\s*(.+?)(?:$|SUB\s+KELAS|/)",
    re.IGNORECASE,
)
_SUBCLASS_LINE = re.compile(
    r"\bsub\s+kelas\s*[:.]?\s*(\d+\.\d+)\s*(.+?)$",
    re.IGNORECASE,
)


def _slugify(s: str) -> str:
    s = s.lower().strip()
    s = re.sub(r"[^a-z0-9]+", "-", s)
    s = re.sub(r"-+", "-", s).strip("-")
    return s[:80] or "halaman"


def _find_header(lines: list[str]) -> tuple[str | None, str | None]:
    """Return (class_tag, subclass_tag) found on this page, or (None, None)."""
    class_tag = subclass_tag = None
    for line in lines[:15]:
        if class_tag is None:
            m = _CLASS_LINE.search(line)
            if m:
                class_tag = f"{m.group(1).strip()}-{_slugify(m.group(2))}"
        if subclass_tag is None:
            m = _SUBCLASS_LINE.search(line)
            if m:
                subclass_tag = f"{m.group(1).strip()}-{_slugify(m.group(2))}"
        if class_tag and subclass_tag:
            break
    return class_tag, subclass_tag


def extract_chunks(pdf_path: Path) -> list[dict[str, Any]]:
    chunks: list[dict[str, Any]] = []
    current_class: str | None = None
    current_subclass: str | None = None

    with pdfplumber.open(str(pdf_path)) as pdf:
        total = len(pdf.pages)
        print(f"Fornas: {total} pages")
        for i, page in enumerate(pdf.pages):
            page_num = i + 1
            raw = page.extract_text() or ""
            text = raw.strip()
            if not text:
                continue

            lines = [ln.strip() for ln in text.splitlines() if ln.strip()]
            cls, sub = _find_header(lines)
            if cls:
                current_class = cls
            if sub:
                current_subclass = sub

            slug = current_subclass or current_class or f"halaman-{page_num}"
            path_parts = []
            if current_class:
                path_parts.append(current_class)
            if current_subclass and current_subclass != current_class:
                path_parts.append(current_subclass)
            path_parts.append(f"hal-{page_num}")
            section_path = "/".join(path_parts)

            chunks.append(
                {
                    "doc_id": DOC_ID,
                    "page": page_num,
                    "section_slug": slug,
                    "section_path": section_path,
                    "text": text,
                    "year": YEAR,
                    "source_type": SOURCE_TYPE,
                    "score": 0.0,
                    "retrieval_method": "hybrid",
                    "source_url": SOURCE_URL,
                }
            )
            if page_num % 50 == 0:
                print(f"  extracted {page_num}/{total}")

    return chunks


def write_processed(chunks: list[dict[str, Any]]) -> Path:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    out_path = OUT_DIR / f"{DOC_ID}.json"
    out_path.write_text(
        json.dumps(chunks, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    print(f"wrote {len(chunks)} chunks → {out_path} ({out_path.stat().st_size // 1024} KB)")
    return out_path


def upsert_manifest() -> None:
    """Add or update the Fornas record in catalog/manifest.json.

    Uses the existing schema; sets status='indexed' so the default
    UI filters show it. We don't re-read via manifest_append's CLI
    here because we already have the record fields literally — the
    server restart will pick up the new record on next boot.
    """
    data = json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))
    # Pages count from the PDF
    with pdfplumber.open(str(PDF_PATH)) as pdf:
        pages = len(pdf.pages)
    size = PDF_PATH.stat().st_size
    record = {
        "doc_id": DOC_ID,
        "source_type": SOURCE_TYPE,
        "title": TITLE,
        "year": YEAR,
        "authority": AUTHORITY,
        "legal_basis": "UU No. 28/2014 Pasal 42",
        "kepmenkes_number": KEPMENKES,
        "source_url": SOURCE_URL,
        "cache_path": str(PDF_PATH.relative_to(REPO)),
        "sha256": None,
        "file_size_bytes": size,
        "pages": pages,
        "language": "id",
        "status": "indexed",
        "supersedes": [],
        "superseded_by": [],
        "discovered_at": "2026-04-23T00:00:00+00:00",
        "discovered_by": "scripts.ingest_fornas",
        "notes": "Formularium Nasional — BPJS formulary. Ingested via pdfplumber per-page chunking.",
    }

    docs = data.get("documents", [])
    for i, d in enumerate(docs):
        if d.get("doc_id") == DOC_ID:
            docs[i] = record
            break
    else:
        docs.append(record)
    data["documents"] = docs

    MANIFEST_PATH.write_text(
        json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    print(f"manifest: upserted {DOC_ID} ({len(docs)} total documents)")


def main() -> int:
    if not PDF_PATH.exists():
        print(f"PDF missing: {PDF_PATH}", file=sys.stderr)
        return 1
    chunks = extract_chunks(PDF_PATH)
    if not chunks:
        print("extracted 0 chunks — aborting", file=sys.stderr)
        return 1
    write_processed(chunks)
    upsert_manifest()
    return 0


if __name__ == "__main__":
    sys.exit(main())
