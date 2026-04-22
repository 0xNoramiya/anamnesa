"""Refusal reasons — first-class terminal state for every agent.

Per CLAUDE.md: an unfounded clinical answer is worse than a clear refusal.
Every refusal reason below is surfaced to the user in Bahasa Indonesia.
"""

from __future__ import annotations

from enum import StrEnum


class RefusalReason(StrEnum):
    OUT_OF_MEDICAL_SCOPE = "out_of_medical_scope"
    CORPUS_SILENT = "corpus_silent"
    ALL_SUPERSEDED_NO_CURRENT = "all_superseded_no_current"
    CITATIONS_UNVERIFIABLE = "citations_unverifiable"
    PATIENT_SPECIFIC_REQUEST = "patient_specific_request"
    RETRIEVAL_BUDGET_EXHAUSTED = "retrieval_budget_exhausted"
    DRAFTER_BUDGET_EXHAUSTED = "drafter_budget_exhausted"
    VERIFIER_BUDGET_EXHAUSTED = "verifier_budget_exhausted"
    TOKEN_BUDGET_EXHAUSTED = "token_budget_exhausted"
    WALL_CLOCK_EXHAUSTED = "wall_clock_exhausted"
    NORMALIZER_MALFORMED = "normalizer_malformed"


# Bahasa Indonesia user-facing messages. Formal register (Anda, not kamu).
# Kept terse; UI composes a fuller disclaimer around these.
REFUSAL_MESSAGES_ID: dict[RefusalReason, str] = {
    RefusalReason.OUT_OF_MEDICAL_SCOPE: (
        "Pertanyaan ini berada di luar cakupan Anamnesa. "
        "Anamnesa hanya mengutip pedoman klinis Indonesia."
    ),
    RefusalReason.CORPUS_SILENT: (
        "Anamnesa tidak menemukan pedoman Indonesia yang relevan untuk "
        "skenario ini. Silakan rujuk ke literatur internasional atau "
        "konsultasi sejawat dengan mencantumkan keterbatasan ini."
    ),
    RefusalReason.ALL_SUPERSEDED_NO_CURRENT: (
        "Semua pedoman Indonesia yang relevan telah digantikan versi baru, "
        "namun versi penggantinya belum ditemukan dalam katalog Anamnesa. "
        "Anamnesa menolak menjawab dari pedoman yang sudah tidak berlaku."
    ),
    RefusalReason.CITATIONS_UNVERIFIABLE: (
        "Anamnesa tidak dapat memverifikasi kutipan yang dihasilkan terhadap "
        "sumber aslinya. Jawaban tidak ditampilkan untuk menghindari "
        "informasi yang tidak terverifikasi."
    ),
    RefusalReason.PATIENT_SPECIFIC_REQUEST: (
        "Ini adalah keputusan klinis untuk pasien individual. Anamnesa "
        "menyediakan rujukan pedoman, bukan rekomendasi per-pasien. "
        "Silakan gunakan pedoman yang relevan untuk membantu keputusan Anda."
    ),
    RefusalReason.RETRIEVAL_BUDGET_EXHAUSTED: (
        "Pencarian berulang tidak menghasilkan bukti yang cukup. "
        "Anamnesa berhenti untuk menghindari jawaban tanpa dasar."
    ),
    RefusalReason.DRAFTER_BUDGET_EXHAUSTED: (
        "Batas percobaan penyusunan jawaban telah tercapai. Anamnesa "
        "berhenti untuk menghindari jawaban tanpa dasar."
    ),
    RefusalReason.VERIFIER_BUDGET_EXHAUSTED: (
        "Batas percobaan verifikasi telah tercapai. Anamnesa berhenti "
        "untuk menghindari kutipan yang tidak terverifikasi."
    ),
    RefusalReason.TOKEN_BUDGET_EXHAUSTED: (
        "Batas token per-kueri telah tercapai. Coba persempit pertanyaan Anda."
    ),
    RefusalReason.WALL_CLOCK_EXHAUSTED: (
        "Waktu pemrosesan per-kueri telah tercapai. Coba persempit "
        "pertanyaan Anda atau ulangi beberapa saat lagi."
    ),
    RefusalReason.NORMALIZER_MALFORMED: (
        "Anamnesa tidak dapat memahami format pertanyaan Anda. "
        "Coba tulis ulang dengan lebih spesifik."
    ),
}


def message_for(reason: RefusalReason) -> str:
    return REFUSAL_MESSAGES_ID[reason]
