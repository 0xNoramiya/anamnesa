/**
 * UI-chrome i18n dictionary.
 *
 * Scope: navigation, buttons, page titles, section labels, empty
 * states, disclaimers. Clinical content (answer prose, citation chunk
 * text, medical document titles) stays Bahasa regardless of `lang` —
 * Anamnesa's value proposition is provenance against the Indonesian
 * guideline corpus, and translating that content would be dishonest.
 *
 * Keep keys flat and namespaced with dots; a missing translation falls
 * back to the key name itself so developers can spot gaps visually.
 */

export type Lang = "id" | "en";

export const LANGS: Lang[] = ["id", "en"];

export const LANG_LABELS: Record<Lang, string> = {
  id: "Bahasa",
  en: "English",
};

type Dict = Record<string, string>;

const ID: Dict = {
  // Nav
  "nav.navigation": "Navigasi",
  "nav.chat": "Chat",
  "nav.chat.sub": "Mode Agen",
  "nav.search": "Pencarian",
  "nav.search.sub": "Cari cepat",
  "nav.guideline": "Guideline",
  "nav.guideline.sub": "Pustaka dokumen",
  "nav.history": "Riwayat",
  "nav.history.sub": "Kueri tersimpan",
  "nav.favorites": "Favorit",
  "nav.favorites.sub": "Pintasan pribadi",
  "nav.trace": "Agent Track",
  "nav.trace.sub": "Jejak eksekusi",

  // Sidebar footer
  "sidebar.corpus_prefix": "Korpus:",
  "sidebar.docs": "80 dokumen",
  "sidebar.chunks": "8.864 potongan",
  "sidebar.legal": "Basis hukum: UU 28/2014 Ps. 42",
  "sidebar.theme_light": "Mode terang",
  "sidebar.theme_dark": "Mode gelap",
  "sidebar.toggle_language": "English",
  "sidebar.home": "Anamnesa — beranda",

  // TopBar subtitles (role: help users know which section they're in)
  "topbar.chat.title": "Mode Agen",
  "topbar.chat.sub": "agentic RAG · dengan sitasi halaman",
  "topbar.search.title": "Pencarian",
  "topbar.search.sub": "cari cepat · langsung ke korpus · tanpa LLM",
  "topbar.guideline.title": "Pustaka Guideline",
  "topbar.guideline.sub": "80 dokumen · PPK FKTP · PNPK · Kepmenkes",
  "topbar.history.title": "Riwayat",
  "topbar.history.sub": "20 kueri terakhir · disimpan di peramban",
  "topbar.favorites.title": "Favorit",
  "topbar.favorites.sub": "pintasan pribadi · jawaban · kutipan · dokumen",
  "topbar.trace.title": "Agent Track",
  "topbar.trace.sub": "jejak eksekusi · per fase · per tool",

  // Landing
  "landing.cta.open": "Buka aplikasi →",
  "landing.cta.example": "Lihat contoh",
  "landing.cta.explore": "Jelajahi 80 dokumen",
  "landing.hero.h1.line1": "Pedoman klinis Indonesia,",
  "landing.hero.h1.line2": "dengan sitasi halaman.",
  "landing.hero.sub":
    "Tanya dalam Bahasa Indonesia. Setiap jawaban mengutip halaman spesifik dari PPK FKTP, PNPK, atau Kepmenkes. Bila korpus tidak memuat jawabannya, kami menolak dengan jujur.",
  "landing.hero.stat":
    "<strong>80 dokumen</strong> dari arsip Kemenkes RI. Gratis, tanpa pendaftaran.",
  "landing.features.cited.title": "Setiap klaim dikutip",
  "landing.features.cited.body":
    "Tidak ada paragraf tanpa sumber. Tap angka [N] untuk melompat ke kartu referensi, klik untuk membuka PDF di halaman tepat.",
  "landing.features.flags.title": "Bendera masa berlaku",
  "landing.features.flags.body":
    "Pedoman yang sudah berusia lebih dari lima tahun ditandai otomatis. Dokumen yang sudah diganti menampilkan versi terbaru.",
  "landing.features.refuse.title": "Penolakan, bukan halusinasi",
  "landing.features.refuse.body":
    "Bila korpus tidak memuat jawaban, Anamnesa menolak menjawab dan menampilkan dokumen paling dekat yang sempat ditemukan.",
  "landing.demo.eyebrow": "CONTOH",
  "landing.demo.h2": "Satu pertanyaan, satu jawaban tersitasi.",
  "landing.demo.q_label": "Pertanyaan",
  "landing.demo.a_label": "Jawaban",
  "landing.demo.q":
    "Pasien dewasa dengan DBD derajat II, trombosit 45.000. Kapan harus dirujuk dari Puskesmas?",
  "landing.demo.a_html":
    "Rujuk bila pasien menunjukkan tanda syok (tekanan nadi ≤ 20 mmHg, akral dingin, CRT &gt; 2 detik)<sup>[1]</sup>, perdarahan spontan masif<sup>[2]</sup>, atau trombosit turun &lt; 100.000 dengan hematokrit meningkat ≥ 20% dari baseline<sup>[1]</sup>.",
  "landing.demo.meta": "2 sitasi · PPK FKTP",
  "landing.legal.eyebrow": "DASAR HUKUM",
  "landing.legal.body_html":
    "<strong>UU No. 28/2014 Pasal 42</strong> menetapkan peraturan perundang-undangan dan keputusan pejabat pemerintah sebagai <em>public domain</em>. Anamnesa hanya mengindeks dokumen yang sah disebar ulang — PPK FKTP, PNPK, dan Kepmenkes.",
  "landing.cta_band.h2": "Tanya dalam Bahasa Indonesia.",
  "landing.cta_band.sub":
    "Alat rujukan klinis, bukan alat diagnosis. Keputusan tata laksana tetap menjadi kewajiban klinisi.",
  "landing.footer.disclaimer":
    "Alat rujukan klinis, <strong>bukan alat diagnosis</strong>. Keputusan tata laksana tetap menjadi kewajiban klinisi.",
  "landing.footer.copyright": "© 2026 Anamnesa",
  "landing.footer.legal": "UU 28/2014 Ps. 42 · domain publik",

  // Placeholder pages
  "page.history.empty_title": "Belum ada riwayat",
  "page.history.empty_body":
    "Kueri yang Anda ajukan di Mode Agen akan muncul di sini. Tersimpan di <code>localStorage</code>, terbatas 20 entri terakhir per peramban.",
  "page.favorites.empty_eyebrow": "§ FAVORIT KOSONG",
  "page.favorites.empty_title":
    "Tap bintang ★ di jawaban, kutipan, atau dokumen untuk menyimpannya di sini.",
  "page.favorites.empty_body_html":
    "Disimpan di <code>localStorage</code> peramban Anda. Tidak ada server yang melihat koleksi ini.",
  "page.favorites.clear_all": "Hapus semua",
  "page.favorites.section_answers": "Jawaban tersimpan",
  "page.favorites.section_chunks": "Kutipan referensi",
  "page.favorites.section_docs": "Dokumen guideline",
  "page.favorites.empty_answers": "Belum ada jawaban yang disimpan.",
  "page.favorites.empty_chunks": "Simpan kutipan dari kartu referensi di Chat.",
  "page.favorites.empty_docs":
    "Gunakan bintang pada halaman Guideline untuk menandai dokumen.",

  // Agent track
  "page.trace.runs_title": "Jejak terbaru",
  "page.trace.runs_sub": "run · peramban ini",
  "page.trace.no_runs_html":
    "Belum ada run. Tanyakan sesuatu di <a>Chat</a> untuk melihat jejak di sini.",
  "page.trace.pick_run_eyebrow": "§ PILIH RUN",
  "page.trace.pick_run_body":
    "Pilih salah satu kueri di sebelah kiri untuk melihat ringkasan kutipan dan alasan penolakan (bila ada).",
  "page.trace.new_run": "Mulai run baru →",
  "page.trace.cites_summary": "Ringkasan kutipan",
  "page.trace.no_cites": "Tidak ada kutipan untuk ditampilkan.",
  "page.trace.stat.status": "Status",
  "page.trace.stat.cites": "Sitasi",
  "page.trace.stat.flags": "Bendera",
  "page.trace.stat.cache": "Cache",
  "page.trace.status.refused": "Refused",
  "page.trace.status.cached": "Cache hit",
  "page.trace.status.done": "Answered",
  "page.trace.reason_label": "ALASAN",
  "page.trace.footer_note":
    "Jejak per-fase hanya dipancarkan secara langsung ke trace-rail saat kueri aktif. Riwayat ini merekonstruksi hasil akhir dari cache lokal.",
};

const EN: Dict = {
  // Nav
  "nav.navigation": "Navigate",
  "nav.chat": "Chat",
  "nav.chat.sub": "Agentic mode",
  "nav.search": "Search",
  "nav.search.sub": "Fast keyword lookup",
  "nav.guideline": "Guideline",
  "nav.guideline.sub": "Document library",
  "nav.history": "History",
  "nav.history.sub": "Saved queries",
  "nav.favorites": "Favorites",
  "nav.favorites.sub": "Personal shortcuts",
  "nav.trace": "Agent Track",
  "nav.trace.sub": "Execution traces",

  "sidebar.corpus_prefix": "Corpus:",
  "sidebar.docs": "80 documents",
  "sidebar.chunks": "8,864 chunks",
  "sidebar.legal": "Legal basis: UU 28/2014 Art. 42",
  "sidebar.theme_light": "Light mode",
  "sidebar.theme_dark": "Dark mode",
  "sidebar.toggle_language": "Bahasa",
  "sidebar.home": "Anamnesa — home",

  "topbar.chat.title": "Agentic mode",
  "topbar.chat.sub": "agentic RAG with page-level citations",
  "topbar.search.title": "Search",
  "topbar.search.sub": "fast lookup · direct corpus hit · no LLM",
  "topbar.guideline.title": "Guideline library",
  "topbar.guideline.sub": "80 documents · PPK FKTP · PNPK · Kepmenkes",
  "topbar.history.title": "History",
  "topbar.history.sub": "your last 20 queries · stored in this browser",
  "topbar.favorites.title": "Favorites",
  "topbar.favorites.sub": "personal shortcuts · answers · citations · documents",
  "topbar.trace.title": "Agent Track",
  "topbar.trace.sub": "execution trace · per phase · per tool",

  // Landing
  "landing.cta.open": "Open app →",
  "landing.cta.example": "See an example",
  "landing.cta.explore": "Browse 80 documents",
  "landing.hero.h1.line1": "Indonesian clinical guidelines,",
  "landing.hero.h1.line2": "cited to the page.",
  "landing.hero.sub":
    "Ask in Bahasa Indonesia. Every answer cites a specific page of an adopted PPK FKTP, PNPK, or Kepmenkes document. When the corpus has nothing to say, Anamnesa refuses — honestly.",
  "landing.hero.stat":
    "<strong>80 documents</strong> from the Kemenkes RI archive. Free, no signup.",
  "landing.features.cited.title": "Every claim cited",
  "landing.features.cited.body":
    "No paragraph without a source. Tap the [N] marker to jump to its reference card, then click to open the PDF at the exact page.",
  "landing.features.flags.title": "Currency flags",
  "landing.features.flags.body":
    "Guidelines older than five years are flagged automatically. Superseded documents surface the newer replacement.",
  "landing.features.refuse.title": "Refusal, not hallucination",
  "landing.features.refuse.body":
    "When the corpus doesn't cover the question, Anamnesa refuses to answer and shows the closest documents it did find.",
  "landing.demo.eyebrow": "EXAMPLE",
  "landing.demo.h2": "One question, one cited answer.",
  "landing.demo.q_label": "Question",
  "landing.demo.a_label": "Answer",
  "landing.demo.q":
    "Adult patient with DHF grade II, platelets 45,000. When should they be referred from a Puskesmas?",
  "landing.demo.a_html":
    "Refer if the patient shows signs of shock (pulse pressure ≤ 20 mmHg, cold extremities, CRT &gt; 2 s)<sup>[1]</sup>, major spontaneous bleeding<sup>[2]</sup>, or platelets dropping below 100,000 with hematocrit rising ≥ 20% from baseline<sup>[1]</sup>.",
  "landing.demo.meta": "2 citations · PPK FKTP",
  "landing.legal.eyebrow": "LEGAL BASIS",
  "landing.legal.body_html":
    "<strong>Indonesian Law No. 28/2014, Article 42</strong> places government regulations and official decisions in the <em>public domain</em>. Anamnesa only indexes documents that can lawfully be redistributed — PPK FKTP, PNPK, and Kepmenkes.",
  "landing.cta_band.h2": "Ask in Bahasa Indonesia.",
  "landing.cta_band.sub":
    "A clinical reference, not a diagnostic tool. Treatment decisions remain the clinician's responsibility.",
  "landing.footer.disclaimer":
    "A clinical reference, <strong>not a diagnostic tool</strong>. Treatment decisions remain the clinician's responsibility.",
  "landing.footer.copyright": "© 2026 Anamnesa",
  "landing.footer.legal": "UU 28/2014 Art. 42 · public domain",

  "page.history.empty_title": "No history yet",
  "page.history.empty_body":
    "Queries you run in Agentic mode will appear here — stored in <code>localStorage</code>, capped at the 20 most recent per browser.",
  "page.favorites.empty_eyebrow": "§ FAVORITES EMPTY",
  "page.favorites.empty_title":
    "Tap ★ on any answer, citation, or document to pin it here.",
  "page.favorites.empty_body_html":
    "Stored in this browser's <code>localStorage</code>. No server sees this collection.",
  "page.favorites.clear_all": "Clear all",
  "page.favorites.section_answers": "Saved answers",
  "page.favorites.section_chunks": "Saved citations",
  "page.favorites.section_docs": "Saved documents",
  "page.favorites.empty_answers": "No answers saved yet.",
  "page.favorites.empty_chunks":
    "Save citations from the reference cards in Chat.",
  "page.favorites.empty_docs":
    "Use the star on any Guideline document to bookmark it.",

  "page.trace.runs_title": "Recent runs",
  "page.trace.runs_sub": "runs · this browser",
  "page.trace.no_runs_html":
    "No runs yet. Ask something in <a>Chat</a> to see a trace here.",
  "page.trace.pick_run_eyebrow": "§ PICK A RUN",
  "page.trace.pick_run_body":
    "Select a query on the left to see its citation summary and refusal reason (if any).",
  "page.trace.new_run": "Start a new run →",
  "page.trace.cites_summary": "Citation summary",
  "page.trace.no_cites": "No citations to display.",
  "page.trace.stat.status": "Status",
  "page.trace.stat.cites": "Citations",
  "page.trace.stat.flags": "Flags",
  "page.trace.stat.cache": "Cache",
  "page.trace.status.refused": "Refused",
  "page.trace.status.cached": "Cache hit",
  "page.trace.status.done": "Answered",
  "page.trace.reason_label": "REASON",
  "page.trace.footer_note":
    "Per-phase events are only emitted live to the trace rail while a query is active. This view reconstructs the final outcome from the local cache.",
};

const DICTS: Record<Lang, Dict> = { id: ID, en: EN };

export function translate(lang: Lang, key: string): string {
  const dict = DICTS[lang] ?? ID;
  const val = dict[key];
  if (val !== undefined) return val;
  const fallback = ID[key];
  if (fallback !== undefined) return fallback;
  // Last-resort: return the key itself so missing strings are visible.
  return key;
}
