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
    "discovered",
    "downloaded",
    "ingested",
    "indexed",
    "failed",
]


class ManifestRecord(BaseModel):
    """One entry in `catalog/manifest.json` — one document."""

    model_config = ConfigDict(extra="forbid")

    doc_id: str = Field(
        description=(
            "Stable, human-readable id. Convention: "
            "`<source_type>-<year>-<slug>`, e.g. `ppk-fktp-2015` or "
            "`pnpk-dengue-2020`. Must be unique across the manifest."
        ),
    )
    source_type: SourceType
    title: str
    year: int
    authority: str = "Kemenkes RI"

    legal_basis: str = "UU No. 28/2014 Pasal 42"
    kepmenkes_number: str | None = None

    source_url: str
    cache_path: str | None = None
    sha256: str | None = None
    file_size_bytes: int | None = None
    pages: int | None = None
    language: str = "id"

    status: DocStatus = "discovered"

    supersedes: list[str] = Field(default_factory=list)
    superseded_by: list[str] = Field(default_factory=list)

    discovered_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    discovered_by: str = "manual"
    notes: str = ""


class Manifest(BaseModel):
    """Root object of `catalog/manifest.json`."""

    model_config = ConfigDict(extra="forbid")

    schema_version: int = 1
    generated_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    documents: list[ManifestRecord] = Field(default_factory=list)

    def index_by_id(self) -> dict[str, int]:
        return {d.doc_id: i for i, d in enumerate(self.documents)}
