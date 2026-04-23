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
  "landing.features.multiturn.title": "Pertanyaan lanjutan",
  "landing.features.multiturn.body":
    "Tanya lanjutan singkat — \"dan kalau anak?\", \"dosisnya berapa?\" — Anamnesa ingat konteks sebelumnya dan menyitasi pedoman yang tepat untuk populasi baru.",
  "landing.features.fornas.title": "Pencarian Fornas instan",
  "landing.features.fornas.body":
    "Cek status BPJS sebuah obat dalam satu ketukan: Fornas 2023 + halaman + disebut di mana saja dalam pedoman lain.",
  "landing.demo.eyebrow": "CONTOH",
  "landing.demo.h2": "Satu pertanyaan, satu jawaban tersitasi.",
  "landing.demo.q_label": "Pertanyaan",
  "landing.demo.a_label": "Jawaban",
  "landing.demo.q":
    "Pasien dewasa dengan DBD derajat II, trombosit 45.000. Kapan harus dirujuk dari Puskesmas?",
  "landing.demo.a_html":
    "Rujuk bila pasien menunjukkan tanda syok (tekanan nadi ≤ 20 mmHg, akral dingin, CRT &gt; 2 detik)<sup>[1]</sup>, perdarahan spontan masif<sup>[2]</sup>, atau trombosit turun &lt; 100.000 dengan hematokrit meningkat ≥ 20% dari baseline<sup>[1]</sup>.",
  "landing.demo.meta": "2 sitasi · PPK FKTP",
  "landing.demo.followup_label": "LANJUTAN",
  "landing.demo.q2": "dan kalau anak?",
  "landing.demo.a2_html":
    "Pada anak, rujuk segera bila usia &lt; 1 tahun, terdapat syok (derajat III/IV), atau muncul <em>warning signs</em> — letargi, muntah persisten, nyeri abdomen hebat, hepatomegali &gt; 2 cm, atau hematokrit meningkat disertai trombositopenia cepat<sup>[3]</sup>.",
  "landing.demo.meta2": "1 sitasi · PNPK Dengue Anak 2021",
  "landing.cta_band.h2": "Tanya dalam Bahasa Indonesia.",
  "landing.cta_band.sub":
    "Alat rujukan klinis, bukan alat diagnosis. Keputusan tata laksana tetap menjadi kewajiban klinisi.",
  "landing.footer.disclaimer":
    "Alat rujukan klinis, <strong>bukan alat diagnosis</strong>. Keputusan tata laksana tetap menjadi kewajiban klinisi.",
  "landing.footer.copyright": "© 2026 Anamnesa",
  "landing.footer.legal": "UU 28/2014 Ps. 42 · domain publik",

  // Docs pages (legal / mcp / api)
  "docs.back": "Beranda",
  "docs.nav.legal": "Legal",
  "docs.nav.mcp": "MCP",
  "docs.nav.api": "API",

  "legal.eyebrow": "DASAR HUKUM",
  "legal.title": "Mengapa Anamnesa legal mengindeks pedoman Kemenkes.",
  "legal.subtitle":
    "Tidak ada lisensi khusus yang diperlukan. Semua pedoman yang diindeks Anamnesa adalah produk hukum negara yang dinyatakan public domain oleh UU.",
  "legal.pasal42.heading": "UU No. 28 Tahun 2014 Pasal 42",
  "legal.pasal42.body_html":
    "<p>Pasal 42 menyatakan bahwa <strong>tidak ada Hak Cipta</strong> atas:</p><ol><li>hasil rapat terbuka lembaga negara;</li><li><strong>peraturan perundang-undangan</strong>;</li><li>pidato kenegaraan atau pidato pejabat pemerintah;</li><li>putusan pengadilan atau penetapan hakim;</li><li><strong>kitab suci atau simbol keagamaan</strong>.</li></ol><p>Dokumen Kemenkes yang diindeks Anamnesa — <strong>Pedoman Nasional Pelayanan Kedokteran (PNPK)</strong>, <strong>Panduan Praktik Klinis FKTP (PPK FKTP)</strong>, dan <strong>Formularium Nasional (Fornas)</strong> — diterbitkan sebagai Lampiran dari Keputusan Menteri Kesehatan, yaitu keputusan pejabat pemerintah yang memiliki kekuatan hukum <em>peraturan perundang-undangan</em>.</p>",
  "legal.consequences.heading": "Konsekuensi praktis",
  "legal.consequences.body_html":
    "<ul><li><strong>Redistribusi bebas</strong> — pengguna dapat mengunduh, menyalin, membagikan, dan mencetak seluruh dokumen tanpa izin.</li><li><strong>Indexing penuh</strong> — Anamnesa dapat menyimpan, memotong, meng-embed, dan mencari seluruh isi dokumen.</li><li><strong>Reproduksi pasase</strong> — kutipan panjang dalam jawaban agen tidak melanggar Hak Cipta karena tidak ada Hak Cipta yang dilanggar.</li><li><strong>Atribusi baik-praktik</strong> — setiap kutipan tetap menampilkan nama dokumen, tahun, dan halaman. Ini etika ilmiah, bukan kewajiban hukum.</li></ul>",
  "legal.scope.heading": "Yang TIDAK diindeks",
  "legal.scope.body_html":
    "<p>Anamnesa hanya mengindeks dokumen yang jelas masuk kategori Pasal 42. Yang di luar cakupan:</p><ul><li><strong>Konsensus perhimpunan profesi</strong> yang belum diadopsi sebagai PNPK (masih berhak cipta pihak penyusun).</li><li><strong>Textbook kedokteran</strong> dan artikel jurnal (berhak cipta penerbit).</li><li><strong>Slide presentasi pribadi</strong> atau materi pelatihan internal.</li></ul><p>Jika Anda menemukan dokumen dalam katalog Anamnesa yang seharusnya tidak di-index, hubungi rhaikal91@gmail.com.</p>",
  "legal.note":
    "Ringkasan ini merupakan interpretasi penulis. Jika Anda memerlukan kepastian hukum untuk kasus spesifik, konsultasikan ke penasehat hukum.",

  "mcp.eyebrow": "MODEL CONTEXT PROTOCOL",
  "mcp.title": "Anamnesa MCP — pakai retrieval pedoman di Claude Code atau Claude Desktop.",
  "mcp.subtitle":
    "Server MCP lokal yang meng-expose 4 tool grounded di korpus pedoman Indonesia. Drafter di Anamnesa memakai server yang sama; Anda bisa memakainya langsung dari Claude Code untuk pertanyaan klinis sehari-hari.",
  "mcp.install.heading": "Konfigurasi Claude Desktop / Claude Code",
  "mcp.install.body":
    "Tambahkan entri berikut ke file konfigurasi MCP Anda (mis. claude_desktop_config.json):",
  "mcp.install.note":
    "Server membaca indeks LanceDB + BM25 dari ANAMNESA_INDEX_DIR. Clone repo Anamnesa, jalankan scripts/build_index.py sekali, lalu tunjuk path-nya di konfigurasi.",
  "mcp.tools.heading": "Tool yang di-expose",
  "mcp.tools.search.name": "search_guidelines(query, filters?)",
  "mcp.tools.search.body":
    "Hybrid search (vector + BM25) dengan filter doc_ids, source_types, min_year, max_year, conditions, dan section_types. Mengembalikan daftar chunk terurut beserta skor + metode retrieval.",
  "mcp.tools.section.name": "get_full_section(doc_id, section_path)",
  "mcp.tools.section.body":
    "Mengembalikan teks lengkap sebuah section — cocok setelah search_guidelines menunjukkan anchor yang tepat. Text sudah melewati pembersihan watermark / footer sehingga bebas dari artefak PDF.",
  "mcp.tools.pdf.name": "get_pdf_page_url(doc_id, page)",
  "mcp.tools.pdf.body":
    "Mengembalikan URL publik ke PDF pada halaman tertentu. Memakai ANAMNESA_PUBLIC_ORIGIN bila diset, jika tidak file:// lokal.",
  "mcp.tools.supersession.name": "check_supersession(doc_id)",
  "mcp.tools.supersession.body":
    "Mengembalikan status masa berlaku (current | superseded | aging | unknown) dan doc_id pengganti jika ada. Dipakai untuk menandai pedoman yang sudah digantikan oleh edisi lebih baru.",
  "mcp.license":
    "Server MCP di-lisensikan MIT. Korpus public domain (UU 28/2014 Ps. 42).",

  "api.eyebrow": "HTTP API",
  "api.title": "Anamnesa REST API — bangun di atas retrieval dan agen.",
  "api.subtitle":
    "Backend Anamnesa adalah FastAPI biasa. Semua endpoint public, tanpa autentikasi, CORS terbuka. Cocok untuk prototype cepat — bukan untuk beban produksi pihak ketiga.",
  "api.base.heading": "Base URL",
  "api.base.body": "Semua jalur relatif terhadap:",
  "api.query.heading": "Jalankan kueri klinis",
  "api.query.body":
    "Kirim kueri Bahasa Indonesia; orkestrator akan menjalankan Normalizer → Retriever → Drafter → Verifier dan mengirim hasilnya via SSE.",
  "api.stream.heading": "SSE stream untuk kueri yang sedang berjalan",
  "api.stream.body":
    "Event-stream dengan tiga kind: trace (per-agen), partial (delta prose dari Drafter), final (payload lengkap). Aman di-reopen; server menyimpan event terakhir per query_id.",
  "api.search.heading": "Search langsung (tanpa agen)",
  "api.search.body":
    "Retrieval mentah atas korpus — vector, BM25, atau hybrid. Cocok untuk eksperimen retrieval.",
  "api.drug.heading": "Pencarian Fornas instan",
  "api.drug.body":
    "Substring match atas 219 halaman Fornas 2023. Zero-LLM. Mengembalikan halaman-halaman di mana obat disebut dan (opsional) bilang di pedoman mana lagi obat tersebut muncul.",
  "api.guideline.heading": "Akses pedoman per-dokumen",
  "api.guideline.body":
    "HTML ramah mobile atau Markdown ekspor untuk setiap dokumen di katalog. Watermark PDF sudah dibersihkan; TOC dibangun otomatis.",
  "api.stability":
    "API ini milik pribadi dan masih berubah. Fork repo untuk stabilitas — tidak ada jaminan versi atau backward-compatibility.",

  "back_to_home": "Kembali ke beranda",

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

  // Retrieval preview (shown while Drafter + Verifier still running)
  "preview.title": "Dokumen yang sedang diperiksa",
  "preview.sub":
    "Retriever menemukan potongan di bawah ini. Drafter sedang menyusun jawaban tersitasi — Anda bisa membaca sumbernya sambil menunggu.",
  "preview.hits": "potongan",
  "preview.docs": "dokumen",
  "preview.open_pdf": "Buka PDF",

  "streaming.eyebrow": "Drafter sedang menulis",
  "streaming.chars": "karakter",

  // Nav — drug lookup
  "nav.obat": "Obat",
  "nav.obat.sub": "Cari di Fornas",

  // TopBar — drug lookup
  "topbar.obat.title": "Cari Obat",
  "topbar.obat.sub": "Formularium Nasional · BPJS · tanpa LLM",

  // Drug-lookup page
  "obat.source": "Sumber: Formularium Nasional — Kepmenkes HK.01.07/2197/2023",
  "obat.placeholder": "contoh: parasetamol, amoksisilin, metformin, amlodipin",
  "obat.clear": "Bersihkan",
  "obat.examples": "Contoh",
  "obat.translit":
    "Tidak ada hasil untuk \"{q}\". Anamnesa mencari ejaan Fornas: \"{t}\".",
  "obat.pages_label": "halaman",
  "obat.hits_label": "total kecocokan",
  "obat.page": "Hal.",
  "obat.hit_1": "kecocokan",
  "obat.hit_n": "kecocokan",
  "obat.open_in_doc": "Buka di Fornas",
  "obat.empty.title": "\"{q}\" tidak ditemukan di Fornas 2023.",
  "obat.empty.hint":
    "Obat ini mungkin tidak termasuk dalam daftar BPJS, atau ejaannya berbeda. Coba nama generik.",
  "obat.truncated": "+{n} halaman lagi — persempit pencarian untuk melihatnya.",
  "obat.footnote":
    "Fornas berisi daftar obat yang ditanggung BPJS Kesehatan beserta restriksi peresepan. Cantuman di sini bukan indikasi klinis — rujuk PPK / PNPK untuk indikasi dan dosis.",

  // Cross-doc mentions section
  "obat.mentions.title": "Disebut juga di pedoman lain",
  "obat.mentions.docs_label": "dokumen",
  "obat.mentions.caption":
    "Halaman di PPK / PNPK / Pedoman Program yang menyebut obat ini — konteks klinis di luar Fornas (indikasi, posologi, rekomendasi lini).",
  "obat.mentions.open": "Buka halaman",
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
  "landing.features.multiturn.title": "Follow-up questions",
  "landing.features.multiturn.body":
    "Ask terse follow-ups — \"and for children?\", \"what's the dose?\" — Anamnesa keeps prior context and cites the right guideline for the new population.",
  "landing.features.fornas.title": "Instant Fornas lookup",
  "landing.features.fornas.body":
    "Check a drug's BPJS status in one tap: Fornas 2023 + page + mentions across other guidelines.",
  "landing.demo.eyebrow": "EXAMPLE",
  "landing.demo.h2": "One question, one cited answer.",
  "landing.demo.q_label": "Question",
  "landing.demo.a_label": "Answer",
  "landing.demo.q":
    "Adult patient with DHF grade II, platelets 45,000. When should they be referred from a Puskesmas?",
  "landing.demo.a_html":
    "Refer if the patient shows signs of shock (pulse pressure ≤ 20 mmHg, cold extremities, CRT &gt; 2 s)<sup>[1]</sup>, major spontaneous bleeding<sup>[2]</sup>, or platelets dropping below 100,000 with hematocrit rising ≥ 20% from baseline<sup>[1]</sup>.",
  "landing.demo.meta": "2 citations · PPK FKTP",
  "landing.demo.followup_label": "FOLLOW-UP",
  "landing.demo.q2": "and for children?",
  "landing.demo.a2_html":
    "For children, refer immediately if age &lt; 1 year, shock is present (grade III/IV), or <em>warning signs</em> appear — lethargy, persistent vomiting, severe abdominal pain, hepatomegaly &gt; 2 cm, or rising hematocrit with rapid thrombocytopenia<sup>[3]</sup>.",
  "landing.demo.meta2": "1 citation · PNPK Dengue Anak 2021",
  "landing.cta_band.h2": "Ask in Bahasa Indonesia.",
  "landing.cta_band.sub":
    "A clinical reference, not a diagnostic tool. Treatment decisions remain the clinician's responsibility.",
  "landing.footer.disclaimer":
    "A clinical reference, <strong>not a diagnostic tool</strong>. Treatment decisions remain the clinician's responsibility.",
  "landing.footer.copyright": "© 2026 Anamnesa",
  "landing.footer.legal": "UU 28/2014 Art. 42 · public domain",

  // Docs pages
  "docs.back": "Home",
  "docs.nav.legal": "Legal",
  "docs.nav.mcp": "MCP",
  "docs.nav.api": "API",

  "legal.eyebrow": "LEGAL BASIS",
  "legal.title": "Why Anamnesa can lawfully index every Kemenkes guideline.",
  "legal.subtitle":
    "No special license is required. Every document in the Anamnesa catalog is a product of Indonesian state law, declared public-domain by statute.",
  "legal.pasal42.heading": "Law No. 28 of 2014, Article 42",
  "legal.pasal42.body_html":
    "<p>Article 42 of Indonesia's Copyright Law states that <strong>no copyright subsists</strong> in:</p><ol><li>minutes of open sessions of state institutions;</li><li><strong>legislation and regulations</strong>;</li><li>state speeches or speeches of government officials;</li><li>court rulings or judicial decisions;</li><li><strong>scripture or religious symbols</strong>.</li></ol><p>The Ministry of Health documents indexed by Anamnesa — <strong>National Clinical Practice Guidelines (PNPK)</strong>, <strong>Primary-Care Clinical Practice Guidelines (PPK FKTP)</strong>, and the <strong>National Formulary (Fornas)</strong> — are issued as Annexes to Ministerial Decrees. Those decrees carry the legal force of regulations and therefore fall squarely under Article 42.</p>",
  "legal.consequences.heading": "What this means in practice",
  "legal.consequences.body_html":
    "<ul><li><strong>Free redistribution</strong> — users may download, copy, share, and print any document without permission.</li><li><strong>Full indexing</strong> — Anamnesa can store, chunk, embed, and search the entire content.</li><li><strong>Passage reproduction</strong> — long quotations in agent answers do not infringe copyright because no copyright exists to infringe.</li><li><strong>Attribution is good practice</strong> — every citation still shows document name, year, and page. That's academic etiquette, not a legal requirement.</li></ul>",
  "legal.scope.heading": "What is NOT indexed",
  "legal.scope.body_html":
    "<p>Anamnesa only indexes documents that clearly fall under Article 42. Out of scope:</p><ul><li><strong>Specialty-society consensus documents</strong> not adopted as PNPK (authorship copyright still applies).</li><li><strong>Medical textbooks</strong> and journal articles (publisher copyright).</li><li><strong>Personal presentation slides</strong> or internal training materials.</li></ul><p>If you spot a document in our catalog that shouldn't be there, email rhaikal91@gmail.com.</p>",
  "legal.note":
    "This is the author's interpretation. For definitive legal guidance on a specific case, consult qualified counsel.",

  "mcp.eyebrow": "MODEL CONTEXT PROTOCOL",
  "mcp.title": "Anamnesa MCP — use the guideline retriever from Claude Code or Claude Desktop.",
  "mcp.subtitle":
    "A local MCP server exposing 4 tools grounded in the Indonesian guideline corpus. Anamnesa's own Drafter agent uses the same server; you can wire it into your Claude client for everyday clinical questions.",
  "mcp.install.heading": "Claude Desktop / Claude Code config",
  "mcp.install.body":
    "Add the following entry to your MCP config file (e.g. claude_desktop_config.json):",
  "mcp.install.note":
    "The server reads the LanceDB + BM25 index from ANAMNESA_INDEX_DIR. Clone the repo, run scripts/build_index.py once, and point the config at that path.",
  "mcp.tools.heading": "Exposed tools",
  "mcp.tools.search.name": "search_guidelines(query, filters?)",
  "mcp.tools.search.body":
    "Hybrid (vector + BM25) search with filters for doc_ids, source_types, min_year, max_year, conditions, and section_types. Returns ranked chunks with scores and retrieval method.",
  "mcp.tools.section.name": "get_full_section(doc_id, section_path)",
  "mcp.tools.section.body":
    "Returns the full text of one section — ideal after search_guidelines surfaces the right anchor. Text is watermark/footer-cleaned so it's free of PDF-extraction artifacts.",
  "mcp.tools.pdf.name": "get_pdf_page_url(doc_id, page)",
  "mcp.tools.pdf.body":
    "Returns a public URL to the PDF at a specific page. Uses ANAMNESA_PUBLIC_ORIGIN when set, otherwise a local file:// path.",
  "mcp.tools.supersession.name": "check_supersession(doc_id)",
  "mcp.tools.supersession.body":
    "Returns currency status (current | superseded | aging | unknown) and the replacement doc_id when one exists. Used to flag guidelines superseded by newer editions.",
  "mcp.license":
    "The MCP server is MIT-licensed. Corpus is public-domain under UU 28/2014 Art. 42.",

  "api.eyebrow": "HTTP API",
  "api.title": "Anamnesa REST API — build on top of the retriever and agents.",
  "api.subtitle":
    "The Anamnesa backend is a plain FastAPI app. All endpoints are public, unauthenticated, with open CORS. Suitable for prototyping — not for third-party production load.",
  "api.base.heading": "Base URL",
  "api.base.body": "All paths are relative to:",
  "api.query.heading": "Run a clinical query",
  "api.query.body":
    "Submit a Bahasa Indonesia query; the orchestrator runs Normalizer → Retriever → Drafter → Verifier and streams results via SSE.",
  "api.stream.heading": "SSE stream for a running query",
  "api.stream.body":
    "Event-stream with three kinds: trace (per-agent), partial (streaming Drafter prose), final (full payload). Safe to re-open — the server retains the last event per query_id.",
  "api.search.heading": "Direct search (no agents)",
  "api.search.body":
    "Raw retrieval over the corpus — vector, BM25, or hybrid. Useful for retrieval experiments.",
  "api.drug.heading": "Instant Fornas lookup",
  "api.drug.body":
    "Substring search over the 219 pages of Fornas 2023. Zero-LLM. Returns pages where the drug is mentioned and (optionally) which other guidelines also mention it.",
  "api.guideline.heading": "Per-document access",
  "api.guideline.body":
    "Mobile-friendly HTML or Markdown export for any document in the catalog. PDF watermark noise is already cleaned; a TOC is built automatically.",
  "api.stability":
    "This API is personal and still shifting. Fork the repo if you need stability — no versioning or backward-compatibility promises.",

  "back_to_home": "Back to home",

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

  "preview.title": "Documents under review",
  "preview.sub":
    "The retriever surfaced these passages. The drafter is composing the cited answer — you can start reading the sources while you wait.",
  "preview.hits": "hits",
  "preview.docs": "documents",
  "preview.open_pdf": "Open PDF",

  "streaming.eyebrow": "Drafter is writing",
  "streaming.chars": "chars",

  "nav.obat": "Drug lookup",
  "nav.obat.sub": "BPJS formulary",

  "topbar.obat.title": "Drug lookup",
  "topbar.obat.sub": "National formulary · BPJS · no LLM",

  "obat.source": "Source: Formularium Nasional — Kepmenkes HK.01.07/2197/2023",
  "obat.placeholder": "e.g. parasetamol, amoksisilin, metformin, amlodipin",
  "obat.clear": "Clear",
  "obat.examples": "Try",
  "obat.translit":
    "No hits for \"{q}\". Searched the Fornas spelling: \"{t}\".",
  "obat.pages_label": "pages",
  "obat.hits_label": "matches",
  "obat.page": "Page",
  "obat.hit_1": "match",
  "obat.hit_n": "matches",
  "obat.open_in_doc": "Open in Fornas",
  "obat.empty.title": "\"{q}\" not found in Fornas 2023.",
  "obat.empty.hint":
    "The drug may not be on the BPJS formulary, or the spelling is different. Try the generic name.",
  "obat.truncated": "+{n} more pages — narrow the search to see them.",
  "obat.footnote":
    "Fornas lists drugs covered by BPJS with prescribing restrictions. Listings here are not clinical indications — consult PPK / PNPK for indication and dose.",

  "obat.mentions.title": "Also mentioned in other guidelines",
  "obat.mentions.docs_label": "documents",
  "obat.mentions.caption":
    "Pages in PPK / PNPK / Pedoman Program that mention this drug — clinical context beyond Fornas (indications, posology, line-of-therapy).",
  "obat.mentions.open": "Open page",
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
