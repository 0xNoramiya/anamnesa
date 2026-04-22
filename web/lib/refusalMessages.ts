// Mirrors core/refusals.py:REFUSAL_MESSAGES_ID. Bahasa Indonesia,
// formal register. Fallback string if the enum expands on the server
// before this file catches up.

import type { RefusalReason } from "./types";

export const REFUSAL_MESSAGES_ID: Record<RefusalReason, string> = {
  out_of_medical_scope:
    "Pertanyaan ini berada di luar cakupan Anamnesa. Anamnesa hanya mengutip pedoman klinis Indonesia.",
  corpus_silent:
    "Anamnesa tidak menemukan pedoman Indonesia yang relevan untuk skenario ini. Silakan rujuk ke literatur internasional atau konsultasi sejawat dengan mencantumkan keterbatasan ini.",
  all_superseded_no_current:
    "Semua pedoman Indonesia yang relevan telah digantikan versi baru, namun versi penggantinya belum ditemukan dalam katalog Anamnesa. Anamnesa menolak menjawab dari pedoman yang sudah tidak berlaku.",
  citations_unverifiable:
    "Anamnesa tidak dapat memverifikasi kutipan yang dihasilkan terhadap sumber aslinya. Jawaban tidak ditampilkan untuk menghindari informasi yang tidak terverifikasi.",
  patient_specific_request:
    "Ini adalah keputusan klinis untuk pasien individual. Anamnesa menyediakan rujukan pedoman, bukan rekomendasi per-pasien. Silakan gunakan pedoman yang relevan untuk membantu keputusan Anda.",
  retrieval_budget_exhausted:
    "Pencarian berulang tidak menghasilkan bukti yang cukup. Anamnesa berhenti untuk menghindari jawaban tanpa dasar.",
  drafter_budget_exhausted:
    "Batas percobaan penyusunan jawaban telah tercapai. Anamnesa berhenti untuk menghindari jawaban tanpa dasar.",
  verifier_budget_exhausted:
    "Batas percobaan verifikasi telah tercapai. Anamnesa berhenti untuk menghindari kutipan yang tidak terverifikasi.",
  token_budget_exhausted:
    "Batas token per-kueri telah tercapai. Coba persempit pertanyaan Anda.",
  wall_clock_exhausted:
    "Waktu pemrosesan per-kueri telah tercapai. Coba persempit pertanyaan Anda atau ulangi beberapa saat lagi.",
  normalizer_malformed:
    "Anamnesa tidak dapat memahami format pertanyaan Anda. Coba tulis ulang dengan lebih spesifik.",
};
