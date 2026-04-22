"""20 eval queries drawn from typical Banjarmasin ED/GP scenarios.

`eval/queries.yaml` would be the ideal home per CLAUDE.md, but we don't
want to drag in PyYAML for one static list. A Python module with Pydantic
validation gives the same shape with zero new deps.

Categories:
  - grounded  (15) — should produce a cited Bahasa answer from an
    ingested doc
  - aging     (3)  — same, but the cited doc is ≥5 years old; the system
    must flag `currency_flags[*].status == "aging"` on at least one
  - absent    (2)  — the corpus has no Indonesian guideline for this
    topic; the system must refuse with `corpus_silent`

Bahasa note: queries are colloquial-formal, the register an Indonesian
doctor would actually type on a phone between patients. Mix of common
abbreviations (DBD, TB, SKA, DM, HT) and full terms.
"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from core.refusals import RefusalReason

Category = Literal["grounded", "aging", "absent"]


class QueryExpectation(BaseModel):
    """Machine-checkable expectations for a single eval query."""

    model_config = ConfigDict(extra="forbid")

    refusal_reason: RefusalReason | None = None
    min_citations: int = 1
    expected_source_types: list[str] | None = None
    expected_doc_ids_any_of: list[str] | None = None
    currency_must_include: str | None = None  # e.g. "aging"
    must_contain_keywords: list[str] = Field(default_factory=list)


class EvalQuery(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str
    category: Category
    query: str
    expected: QueryExpectation
    rationale: str = ""


# ---------------------------------------------------------------------------
# The 20 queries
# ---------------------------------------------------------------------------


QUERIES: list[EvalQuery] = [
    # ---- grounded: ED acute (7) ----
    EvalQuery(
        id="q001",
        category="grounded",
        query=(
            "Bayi baru lahir tidak menangis, apnea, heart rate <100. "
            "Langkah resusitasi awal dalam 60 detik pertama?"
        ),
        expected=QueryExpectation(
            expected_source_types=["pnpk"],
            expected_doc_ids_any_of=["pnpk-asfiksia-2019", "pnpk-resusitasi-bblr-2018"],
            currency_must_include="aging",
            must_contain_keywords=["menit emas", "VTP"],
        ),
        rationale="Tests neonatal-resuscitation path; both source PNPKs are 2018-2019 (aging).",
    ),
    EvalQuery(
        id="q002",
        category="grounded",
        query="DBD derajat II anak 8 tahun, BB 20 kg, tata laksana cairan kristaloid awal?",
        expected=QueryExpectation(
            expected_source_types=["pnpk", "ppk_fktp"],
            expected_doc_ids_any_of=["pnpk-dengue-anak-2021", "ppk-fktp-2015"],
            must_contain_keywords=["kristaloid"],
        ),
        rationale="Pediatric DBD fluid resus — high-frequency ED presentation.",
    ),
    EvalQuery(
        id="q003",
        category="grounded",
        query="Syok pada DBD dewasa, dosis awal cairan resusitasi dan targetnya?",
        expected=QueryExpectation(
            expected_source_types=["pnpk"],
            expected_doc_ids_any_of=["pnpk-dengue-dewasa-2020"],
        ),
        rationale="Adult DBD shock, 2020 PNPK.",
    ),
    EvalQuery(
        id="q004",
        category="grounded",
        query=(
            "Pasien sepsis dewasa di IGD, bundel 1 jam — "
            "antibiotik empirik dan resusitasi cairan?"
        ),
        expected=QueryExpectation(
            expected_source_types=["pnpk"],
            expected_doc_ids_any_of=["pnpk-sepsis-2017"],
        ),
        rationale="Adult sepsis bundle — classic ED scenario.",
    ),
    EvalQuery(
        id="q005",
        category="grounded",
        query="Sepsis pediatrik, target resusitasi cairan dan pemilihan inotropik?",
        expected=QueryExpectation(
            expected_source_types=["pnpk"],
            expected_doc_ids_any_of=["pnpk-sepsis-anak-2021"],
        ),
        rationale="Pediatric sepsis bundle; PNPK 2021.",
    ),
    EvalQuery(
        id="q006",
        category="grounded",
        query="Pneumonia komunitas dewasa tanpa komorbid, pilihan antibiotik empirik rawat jalan?",
        expected=QueryExpectation(
            expected_source_types=["pnpk", "ppk_fktp"],
            expected_doc_ids_any_of=["pnpk-pneumonia-dewasa-2023", "ppk-fktp-2015"],
        ),
        rationale="Common ambulatory pneumonia scenario.",
    ),
    EvalQuery(
        id="q007",
        category="grounded",
        query=(
            "STEMI presentasi <12 jam di fasilitas tanpa kapasitas PCI, "
            "indikasi dan kontraindikasi fibrinolitik?"
        ),
        expected=QueryExpectation(
            expected_source_types=["pnpk"],
            expected_doc_ids_any_of=["pnpk-sindroma-koroner-akut-2019"],
        ),
        rationale="STEMI reperfusion decision at non-PCI center.",
    ),
    # ---- grounded: chronic / pediatric (4) ----
    EvalQuery(
        id="q008",
        category="grounded",
        query=(
            "DM tipe 2 dewasa baru terdiagnosis, HbA1c 8.5%. "
            "Tata laksana farmakologis lini pertama?"
        ),
        expected=QueryExpectation(
            expected_source_types=["pnpk", "ppk_fktp"],
            expected_doc_ids_any_of=[
                "pnpk-diabetes-melitus-tipe-2-dewasa-2020",
                "ppk-fktp-2015",
            ],
        ),
        rationale="DM T2 first-line — ubiquitous GP scenario.",
    ),
    EvalQuery(
        id="q009",
        category="grounded",
        query=(
            "Hipertensi esensial dewasa tanpa komorbid, TD 160/100 mmHg. "
            "Obat antihipertensi lini pertama dan target?"
        ),
        expected=QueryExpectation(
            expected_source_types=["pnpk", "ppk_fktp"],
            expected_doc_ids_any_of=["pnpk-hipertensi-dewasa-2021", "ppk-fktp-2015"],
        ),
        rationale="HT stage 2 first-line — very common.",
    ),
    EvalQuery(
        id="q010",
        category="grounded",
        query="Bayi prematur 32 minggu dengan apnea of prematurity, pilihan terapi medikamentosa?",
        expected=QueryExpectation(
            expected_source_types=["pnpk"],
            expected_doc_ids_any_of=["pnpk-resusitasi-bblr-2018"],
        ),
        rationale="Prematurity apnea — NICU/ED shared presentation.",
    ),
    EvalQuery(
        id="q011",
        category="grounded",
        query=(
            "Ibu hamil 32 minggu dengan TD 160/110 mmHg, proteinuria +3, "
            "sakit kepala. Tata laksana preeklampsia berat?"
        ),
        expected=QueryExpectation(
            expected_source_types=["pnpk"],
            expected_doc_ids_any_of=["pnpk-komplikasi-kehamilan-2017"],
        ),
        rationale="Severe preeclampsia — obstetric emergency.",
    ),
    # ---- grounded: trauma / burns (2) ----
    EvalQuery(
        id="q012",
        category="grounded",
        query=(
            "Luka bakar derajat II pada 30% TBSA dewasa, "
            "kalkulasi kebutuhan cairan resusitasi 24 jam pertama?"
        ),
        expected=QueryExpectation(
            expected_source_types=["pnpk"],
            expected_doc_ids_any_of=["pnpk-luka-bakar-2019"],
        ),
        rationale="Burn fluid resuscitation — Parkland or modified formula.",
    ),
    EvalQuery(
        id="q013",
        category="grounded",
        query="Cedera kepala ringan dewasa GCS 14. Kriteria indikasi CT scan kepala dan rujukan?",
        expected=QueryExpectation(
            expected_source_types=["pnpk"],
            expected_doc_ids_any_of=["pnpk-cidera-otak-traumatik-2022"],
        ),
        rationale="Mild head injury triage.",
    ),
    # ---- grounded: PPK FKTP primary-care conditions (2) ----
    EvalQuery(
        id="q014",
        category="grounded",
        query=(
            "Dewasa dengan migren tanpa aura, serangan akut di Puskesmas. "
            "Pilihan analgetik dan kapan merujuk?"
        ),
        expected=QueryExpectation(
            expected_source_types=["ppk_fktp"],
            expected_doc_ids_any_of=["ppk-fktp-2015"],
        ),
        rationale="Classic Puskesmas presentation; PPK FKTP 2015 (aging).",
    ),
    EvalQuery(
        id="q015",
        category="grounded",
        query=(
            "Anak 2 tahun dengan gastroenteritis akut dan dehidrasi sedang. "
            "Tata laksana rehidrasi oral dan kriteria rujukan?"
        ),
        expected=QueryExpectation(
            expected_source_types=["ppk_fktp"],
            expected_doc_ids_any_of=["ppk-fktp-2015"],
        ),
        rationale="Pediatric GE — common Puskesmas scenario.",
    ),
    # ---- aging (3): cited doc ≥5 years old in 2026 → aging flag ----
    EvalQuery(
        id="q016",
        category="aging",
        query="Pasien TB paru dewasa baru BTA positif, rejimen OAT lini pertama dan durasi?",
        expected=QueryExpectation(
            expected_source_types=["pnpk"],
            expected_doc_ids_any_of=["pnpk-tuberkulosis-2019"],
            currency_must_include="aging",
            must_contain_keywords=["2RHZE", "4RH"],
        ),
        rationale="TB 2019 PNPK is 7y old; must flag aging.",
    ),
    EvalQuery(
        id="q017",
        category="aging",
        query=(
            "HIV dewasa baru terdiagnosis dengan CD4 <200. "
            "Waktu inisiasi ARV dan rejimen lini pertama?"
        ),
        expected=QueryExpectation(
            expected_source_types=["pnpk"],
            expected_doc_ids_any_of=["pnpk-hiv-2019"],
            currency_must_include="aging",
        ),
        rationale="HIV 2019 PNPK — 7y old, aging.",
    ),
    EvalQuery(
        id="q018",
        category="aging",
        query="Malaria falsiparum tanpa komplikasi dewasa. Pilihan ACT lini pertama dan durasi?",
        expected=QueryExpectation(
            expected_source_types=["pnpk"],
            expected_doc_ids_any_of=["pnpk-malaria-2019"],
            currency_must_include="aging",
        ),
        rationale="Malaria 2019 PNPK — aging. ACT regimens evolve.",
    ),
    # ---- absent (2): verified absent in the corpus ----
    EvalQuery(
        id="q019",
        category="absent",
        query=(
            "Skor HAS-BLED untuk menilai risiko perdarahan pada fibrilasi atrium "
            "non-valvular — komponen dan interpretasi menurut pedoman Indonesia?"
        ),
        expected=QueryExpectation(
            refusal_reason=RefusalReason.CORPUS_SILENT,
            min_citations=0,
        ),
        rationale="HAS-BLED not in our corpus; must refuse not hallucinate.",
    ),
    EvalQuery(
        id="q020",
        category="absent",
        query=(
            "Kriteria Wells untuk probabilitas emboli paru — skor dan "
            "interpretasinya menurut pedoman Indonesia?"
        ),
        expected=QueryExpectation(
            refusal_reason=RefusalReason.CORPUS_SILENT,
            min_citations=0,
        ),
        rationale="Wells criteria not in corpus; must refuse.",
    ),
]


def by_id(query_id: str) -> EvalQuery:
    for q in QUERIES:
        if q.id == query_id:
            return q
    raise KeyError(f"no query with id={query_id!r}")


def by_category(category: Category) -> list[EvalQuery]:
    return [q for q in QUERIES if q.category == category]
