"""Catalog manifest schema.

`catalog/manifest.json` is the source-of-truth registry for every document
in the Anamnesa corpus. It is append-heavy during Day-2 crawling (parallel
sub-agents append to it) and read-heavy during ingestion / index builds.

Legal context: every document here is publicly released under
UU No. 28/2014 Pasal 42 (peraturan perundang-undangan + keputusan
pejabat Pemerintah → tidak memiliki hak cipta). See CLAUDE.md > Legal
foundation.
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from core.state import SourceType

DocStatus = Literal[
    "discovered",   # URL known, not yet fetched
    "downloaded",   # PDF in catalog/cache, sha256 computed
    "ingested",     # parsed into catalog/processed/{source}/*.json
    "indexed",      # chunks live in index/lance + bm25
    "failed",       # a processing step failed; see `notes`
]


class ManifestRecord(BaseModel):
    """One entry in `catalog/manifest.json` — one document."""

    model_config = ConfigDict(extra="forbid")

    # --- identity ---
    doc_id: str = Field(
        description=(
            "Stable, human-readable id. Convention: "
            "`<source_type>-<year>-<slug>`, e.g. `ppk-fktp-2015` or "
            "`pnpk-dengue-2020`. Must be unique across the manifest."
        ),
    )
    source_type: SourceType
    title: str                                   # Bahasa Indonesia title
    year: int                                    # source year
    authority: str = "Kemenkes RI"

    # --- legal (always Pasal 42 for hackathon scope) ---
    legal_basis: str = "UU No. 28/2014 Pasal 42"
    kepmenkes_number: str | None = None          # e.g. "HK.02.02/MENKES/514/2015"

    # --- physical document ---
    source_url: str                              # original download URL
    cache_path: str | None = None                # e.g. "catalog/cache/pnpk/dengue-2020.pdf"
    sha256: str | None = None                    # 64 hex chars
    file_size_bytes: int | None = None
    pages: int | None = None
    language: str = "id"

    # --- pipeline state ---
    status: DocStatus = "discovered"

    # --- supersession graph ---
    supersedes: list[str] = Field(default_factory=list)
    superseded_by: list[str] = Field(default_factory=list)

    # --- provenance ---
    discovered_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    discovered_by: str = "manual"                # crawler sub-agent id or "manual"
    notes: str = ""


class Manifest(BaseModel):
    """Root object of `catalog/manifest.json`."""

    model_config = ConfigDict(extra="forbid")

    schema_version: int = 1
    generated_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    documents: list[ManifestRecord] = Field(default_factory=list)

    def index_by_id(self) -> dict[str, int]:
        return {d.doc_id: i for i, d in enumerate(self.documents)}
