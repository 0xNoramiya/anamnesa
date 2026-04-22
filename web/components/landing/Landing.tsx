import Link from "next/link";
import type { ReactNode } from "react";
import { Wordmark } from "@/components/shell/Logo";
import { CurrencyChip, type CurrencyKind } from "@/components/shell/CurrencyChip";

/**
 * Landing page — civic document hero + demos + audience + corpus + CTA.
 * Pure SSR-safe React, no client-only hooks; links to /app/* for the
 * sidebar-nav application surface.
 */
export function Landing() {
  return (
    <div style={{ background: "var(--paper)", color: "var(--ink)", minHeight: "100vh" }}>
      <LandingHeader />
      <LandingHero />
      <LandingDemos />
      <LandingAudience />
      <LandingCorpus />
      <LandingCTA />
      <LandingFooter />
    </div>
  );
}

function LandingHeader() {
  return (
    <div
      style={{
        position: "sticky",
        top: 0,
        zIndex: 10,
        background: "color-mix(in oklch, var(--paper) 92%, transparent)",
        backdropFilter: "blur(8px)",
        WebkitBackdropFilter: "blur(8px)",
        borderBottom: "1px solid var(--rule)",
        padding: "14px clamp(20px, 5vw, 56px)",
        display: "flex",
        alignItems: "center",
        gap: 24,
        flexWrap: "wrap",
      }}
    >
      <Wordmark size={16} />
      <div
        className="mono"
        style={{
          fontSize: 11,
          color: "var(--ink-3)",
          paddingLeft: 14,
          borderLeft: "1px solid var(--rule)",
        }}
      >
        Retrieval pedoman klinis Indonesia
      </div>
      <div style={{ flex: 1, minWidth: 20 }} />
      <nav
        style={{
          display: "flex",
          gap: 22,
          fontSize: 13.5,
          color: "var(--ink-2)",
        }}
      >
        <a style={{ color: "inherit", textDecoration: "none" }} href="#demo">
          Demo
        </a>
        <a style={{ color: "inherit", textDecoration: "none" }} href="#korpus">
          Korpus
        </a>
        <a style={{ color: "inherit", textDecoration: "none" }} href="#dasar-hukum">
          Dasar Hukum
        </a>
      </nav>
      <Link href="/chat" className="btn btn-primary">
        Buka Aplikasi →
      </Link>
    </div>
  );
}

function LandingHero() {
  return (
    <section style={{ padding: "clamp(40px, 8vw, 72px) clamp(20px, 5vw, 56px) 56px", maxWidth: 1280, margin: "0 auto" }}>
      <div style={{ display: "flex", alignItems: "baseline", gap: 14, marginBottom: 28 }}>
        <span
          className="mono"
          style={{ fontSize: 10.5, color: "var(--oxblood)", letterSpacing: "0.14em" }}
        >
          § 01 — IKHTISAR
        </span>
        <div style={{ flex: 1, height: 1, background: "var(--rule)" }} />
        <span className="mono" style={{ fontSize: 10.5, color: "var(--ink-3)" }}>
          v1.4 · April 2026
        </span>
      </div>

      <div
        style={{
          display: "grid",
          gridTemplateColumns: "minmax(0, 1.2fr) minmax(0, 1fr)",
          gap: "clamp(24px, 5vw, 72px)",
          alignItems: "start",
        }}
        className="landing-hero-grid"
      >
        <div>
          <h1
            className="display"
            style={{
              fontSize: "clamp(36px, 6vw, 64px)",
              lineHeight: 1.04,
              margin: 0,
              fontWeight: 500,
              letterSpacing: "-0.025em",
              color: "var(--ink)",
              fontVariationSettings: "'opsz' 60, 'SOFT' 30",
            }}
          >
            Pedoman klinis Indonesia,
            <br />
            <span style={{ fontStyle: "italic", color: "var(--navy)" }}>
              dengan sitasi halaman.
            </span>
          </h1>

          <p
            style={{
              fontSize: 18,
              lineHeight: 1.55,
              marginTop: 26,
              color: "var(--ink-2)",
              maxWidth: 560,
              fontWeight: 400,
            }}
          >
            Anamnesa menjawab pertanyaan klinis berdasarkan PPK FKTP, PNPK, dan
            Kepmenkes — bukan dari ingatan model. Setiap rekomendasi merujuk ke
            halaman spesifik dari dokumen yang diadopsi Kemenkes. Bila korpus
            tidak memuat jawabannya, Anamnesa menolak dengan jujur.
          </p>

          <div
            style={{
              display: "flex",
              gap: 10,
              marginTop: 32,
              alignItems: "center",
              flexWrap: "wrap",
            }}
          >
            <Link
              href="/chat"
              className="btn btn-primary"
              style={{ padding: "12px 18px", fontSize: 14 }}
            >
              Coba di browser →
            </Link>
            <a
              href="#demo"
              className="btn btn-ghost"
              style={{ padding: "12px 18px", fontSize: 14 }}
            >
              Lihat demo kueri
            </a>
            <span
              className="mono"
              style={{ fontSize: 11, color: "var(--ink-3)", marginLeft: 8 }}
            >
              Gratis · tanpa pendaftaran
            </span>
          </div>

          <div
            id="dasar-hukum"
            style={{
              marginTop: 44,
              padding: "14px 16px",
              borderLeft: "2px solid var(--oxblood)",
              background: "var(--paper-2)",
              fontSize: 13,
              color: "var(--ink-2)",
              lineHeight: 1.5,
            }}
          >
            <span
              className="mono"
              style={{ fontSize: 10.5, color: "var(--oxblood)", letterSpacing: "0.12em" }}
            >
              DASAR HUKUM
            </span>
            <div style={{ marginTop: 4 }}>
              <strong>UU No. 28/2014 Pasal 42</strong> menetapkan peraturan
              perundang-undangan sebagai <em>public domain</em>. Anamnesa hanya
              mengindeks dokumen yang sah disebar ulang.
            </div>
          </div>
        </div>

        <DocumentPreview />
      </div>
    </section>
  );
}

function DocumentPreview() {
  return (
    <div
      style={{
        background: "var(--paper-2)",
        border: "1px solid var(--rule)",
        padding: 0,
        borderRadius: 2,
        position: "relative",
        boxShadow: "0 1px 0 var(--rule-2), 0 14px 30px -18px rgba(15,27,45,0.18)",
      }}
    >
      <div
        style={{
          display: "flex",
          alignItems: "center",
          gap: 8,
          padding: "10px 14px",
          borderBottom: "1px solid var(--rule)",
          background: "var(--paper-3)",
        }}
      >
        <div style={{ width: 8, height: 8, borderRadius: "50%", background: "var(--rule-2)" }} />
        <div style={{ width: 8, height: 8, borderRadius: "50%", background: "var(--rule-2)" }} />
        <div style={{ width: 8, height: 8, borderRadius: "50%", background: "var(--rule-2)" }} />
        <span
          className="mono"
          style={{ fontSize: 10.5, color: "var(--ink-3)", marginLeft: 8 }}
        >
          anamnesa · mode agen
        </span>
      </div>

      <div style={{ padding: "16px 18px", borderBottom: "1px solid var(--rule)" }}>
        <div className="label" style={{ marginBottom: 6 }}>
          Pertanyaan
        </div>
        <div style={{ fontSize: 14, color: "var(--ink)", lineHeight: 1.5 }}>
          Pasien dewasa datang dengan DBD derajat II dan trombosit 45.000. Kapan
          harus dirujuk dari Puskesmas?
        </div>
      </div>

      <div style={{ padding: "16px 18px" }}>
        <div className="label" style={{ marginBottom: 8 }}>
          Jawaban
        </div>
        <div style={{ fontSize: 14, lineHeight: 1.65, color: "var(--ink)" }}>
          Rujuk bila pasien menunjukkan tanda syok (tekanan nadi ≤ 20 mmHg, akral
          dingin, CRT &gt; 2 detik)<span className="cite">1</span>, perdarahan
          spontan masif<span className="cite">2</span>, atau trombosit turun &lt;
          100.000 dengan hematokrit meningkat ≥ 20% dari baseline
          <span className="cite">1</span>. Pada derajat II tanpa tanda syok, rawat
          di FKTP dengan monitoring hematokrit setiap 4–6 jam
          <span className="cite">3</span>.
        </div>

        <div style={{ marginTop: 14, display: "flex", gap: 8, flexWrap: "wrap" }}>
          <CurrencyChip kind="current" year={2023} />
          <span
            className="mono"
            style={{ fontSize: 10.5, color: "var(--ink-3)", alignSelf: "center" }}
          >
            3 sitasi · PPK FKTP · dari cache · 2 menit lalu
          </span>
        </div>

        <div style={{ marginTop: 16, display: "flex", flexDirection: "column", gap: 8 }}>
          <MiniRef n={1} doc="PPK FKTP 2023 · Demam Berdarah Dengue" page="hal. 142" />
          <MiniRef n={2} doc="PPK FKTP 2023 · Demam Berdarah Dengue" page="hal. 145" />
          <MiniRef n={3} doc="Kepmenkes 1456/2023 · Tata Laksana DBD" page="hal. 28" />
        </div>
      </div>
    </div>
  );
}

function MiniRef({ n, doc, page }: { n: number; doc: string; page: string }) {
  return (
    <div
      style={{
        display: "flex",
        alignItems: "center",
        gap: 10,
        padding: "7px 10px",
        background: "var(--paper)",
        border: "1px solid var(--rule)",
        borderRadius: 2,
        fontSize: 12,
      }}
    >
      <span
        className="mono"
        style={{
          background: "var(--navy)",
          color: "var(--paper)",
          padding: "1px 6px",
          fontSize: 10.5,
          fontWeight: 500,
        }}
      >
        {n}
      </span>
      <span style={{ flex: 1, color: "var(--ink)" }}>{doc}</span>
      <span className="mono" style={{ fontSize: 10.5, color: "var(--ink-3)" }}>
        {page}
      </span>
    </div>
  );
}

interface Demo {
  tag: string;
  q: string;
  flag: CurrencyKind;
  year: number | null;
  a: ReactNode;
  meta: string;
}

function LandingDemos() {
  const demos: Demo[] = [
    {
      tag: "BAHASA SEHARI-HARI → JAWABAN TERSITASI",
      q: '"Anak 3 th demam 4 hari, sudah turun tapi jadi lemas, tangan dingin. WADUH."',
      flag: "current",
      year: 2023,
      a: (
        <>
          Tanda syok dengue (warning signs) pada fase kritis. Lakukan cek
          hematokrit, trombosit, dan kapiler segera. Berikan cairan kristaloid{" "}
          <strong>5–7 ml/kg/jam</strong>
          <span className="cite">1</span> dan pertimbangkan rujukan ke fasilitas
          dengan kapasitas rawat inap pediatrik
          <span className="cite">2</span>.
        </>
      ),
      meta: "2 sitasi · <220 ms · tanpa LLM untuk klasifikasi",
    },
    {
      tag: "FLAG MASA BERLAKU + DOKUMEN YANG SUDAH DIGANTI",
      q: "Bagaimana tata laksana TB laten pada dewasa?",
      flag: "superseded",
      year: 2018,
      a: (
        <>
          ⚠ Dokumen utama yang cocok adalah{" "}
          <strong>Pedoman Nasional TB 2018</strong> — <em>sudah diganti</em> oleh
          PNPK TB 2023<span className="cite">1</span>. Rekomendasi terbaru: INH
          300 mg + rifapentin 900 mg sekali seminggu × 12 minggu (rejimen 3HP)
          <span className="cite">2</span>.
        </>
      ),
      meta: "2 sitasi · 1 versi lebih baru tersedia",
    },
    {
      tag: "KORPUS SUNYI → PENOLAKAN JUJUR",
      q: "Apa protokol ECMO pada COVID-19 berat?",
      flag: "withdrawn",
      year: null,
      a: (
        <>
          <strong>Anamnesa menolak menjawab.</strong> Korpus Kemenkes yang
          tersedia tidak memuat protokol ECMO. Topik ini berada di luar PPK FKTP
          dan PNPK yang diindeks. Potongan paling dekat: &ldquo;Manajemen
          COVID-19 berat di ICU&rdquo; (PNPK 2022, hal. 67) — tidak menyebut
          ECMO.
        </>
      ),
      meta: "Refusal-first · tidak ada halusinasi",
    },
  ];

  return (
    <section
      id="demo"
      style={{
        padding: "64px clamp(20px, 5vw, 56px)",
        maxWidth: 1280,
        margin: "0 auto",
        borderTop: "1px solid var(--rule)",
      }}
    >
      <div style={{ display: "flex", alignItems: "baseline", gap: 14, marginBottom: 28 }}>
        <span
          className="mono"
          style={{ fontSize: 10.5, color: "var(--oxblood)", letterSpacing: "0.14em" }}
        >
          § 02 — TIGA CONTOH
        </span>
        <div style={{ flex: 1, height: 1, background: "var(--rule)" }} />
      </div>

      <h2
        className="display"
        style={{
          fontSize: "clamp(28px, 3.6vw, 38px)",
          lineHeight: 1.1,
          margin: "0 0 10px",
          fontWeight: 500,
          letterSpacing: "-0.02em",
          maxWidth: 800,
        }}
      >
        Tiga situasi yang menjelaskan mengapa Anamnesa berbeda.
      </h2>
      <p
        style={{
          fontSize: 15,
          color: "var(--ink-2)",
          lineHeight: 1.55,
          maxWidth: 680,
          marginBottom: 40,
        }}
      >
        Dokter yang membaca pada jam 3 pagi butuh tiga hal: jawaban yang bisa
        diverifikasi, peringatan bila pedomannya usang, dan penolakan yang jujur
        ketika korpus diam.
      </p>

      <div
        style={{
          display: "grid",
          gridTemplateColumns: "repeat(auto-fit, minmax(260px, 1fr))",
          gap: 24,
        }}
      >
        {demos.map((d) => (
          <article
            key={d.tag}
            style={{
              background: "var(--paper-2)",
              border: "1px solid var(--rule)",
              padding: 20,
              borderRadius: 2,
              position: "relative",
            }}
          >
            <div
              className="mono"
              style={{
                fontSize: 9.5,
                color: "var(--ink-3)",
                letterSpacing: "0.12em",
                marginBottom: 14,
                paddingBottom: 10,
                borderBottom: "1px dashed var(--rule)",
              }}
            >
              {d.tag}
            </div>

            <div
              style={{
                fontSize: 13,
                color: "var(--ink)",
                fontStyle: "italic",
                marginBottom: 14,
                lineHeight: 1.5,
              }}
            >
              <span style={{ color: "var(--ink-4)", marginRight: 6 }}>Q.</span>
              {d.q}
            </div>

            <div
              style={{
                fontSize: 13.5,
                color: "var(--ink-2)",
                lineHeight: 1.6,
                marginBottom: 14,
              }}
            >
              {d.a}
            </div>

            <div style={{ display: "flex", gap: 8, alignItems: "center", marginBottom: 8 }}>
              <CurrencyChip kind={d.flag} year={d.year} />
            </div>
            <div className="mono" style={{ fontSize: 10.5, color: "var(--ink-3)" }}>
              {d.meta}
            </div>
          </article>
        ))}
      </div>
    </section>
  );
}

function LandingAudience() {
  const users = [
    { t: "Dokter IGD", d: "Jam 3 pagi, pasien tidak stabil, butuh tata laksana yang bisa dipertanggungjawabkan." },
    { t: "Dokter umum FKTP", d: "Di Puskesmas tanpa akses ke langganan jurnal berbayar berbahasa Inggris." },
    { t: "Residen PPDS", d: "Cross-check rekomendasi dengan pedoman Kemenkes saat menyiapkan presentasi morbiditas." },
    { t: "Apoteker klinis", d: "Verifikasi dosis dan interaksi terhadap PPK resmi sebelum mendispensasi." },
  ];

  return (
    <section
      style={{
        padding: "56px clamp(20px, 5vw, 56px)",
        maxWidth: 1280,
        margin: "0 auto",
        borderTop: "1px solid var(--rule)",
      }}
    >
      <div style={{ display: "flex", alignItems: "baseline", gap: 14, marginBottom: 28 }}>
        <span
          className="mono"
          style={{ fontSize: 10.5, color: "var(--oxblood)", letterSpacing: "0.14em" }}
        >
          § 03 — SIAPA YANG BISA PAKAI
        </span>
        <div style={{ flex: 1, height: 1, background: "var(--rule)" }} />
      </div>
      <h2
        className="display"
        style={{
          fontSize: "clamp(24px, 3vw, 32px)",
          fontWeight: 500,
          margin: "0 0 32px",
          letterSpacing: "-0.02em",
        }}
      >
        Dibangun untuk klinisi yang butuh jawaban <em>tersitasi</em> — bukan{" "}
        <em>plausible</em>.
      </h2>
      <div
        style={{
          display: "grid",
          gridTemplateColumns: "repeat(auto-fit, minmax(200px, 1fr))",
          gap: 20,
        }}
      >
        {users.map((u) => (
          <div
            key={u.t}
            style={{
              padding: "16px 18px",
              background: "var(--paper-2)",
              borderLeft: "2px solid var(--navy)",
            }}
          >
            <div
              className="display"
              style={{ fontSize: 17, fontWeight: 500, marginBottom: 6 }}
            >
              {u.t}
            </div>
            <div style={{ fontSize: 13, color: "var(--ink-2)", lineHeight: 1.5 }}>
              {u.d}
            </div>
          </div>
        ))}
      </div>
    </section>
  );
}

function LandingCorpus() {
  return (
    <section
      id="korpus"
      style={{
        padding: "56px clamp(20px, 5vw, 56px)",
        maxWidth: 1280,
        margin: "0 auto",
        borderTop: "1px solid var(--rule)",
      }}
    >
      <div
        style={{
          display: "grid",
          gridTemplateColumns: "minmax(0, 1fr) minmax(0, 1.4fr)",
          gap: "clamp(24px, 5vw, 56px)",
          alignItems: "start",
        }}
      >
        <div>
          <div
            className="mono"
            style={{
              fontSize: 10.5,
              color: "var(--oxblood)",
              letterSpacing: "0.14em",
              marginBottom: 10,
            }}
          >
            § 04 — KORPUS
          </div>
          <h2
            className="display"
            style={{
              fontSize: "clamp(24px, 3vw, 32px)",
              fontWeight: 500,
              margin: 0,
              letterSpacing: "-0.02em",
              lineHeight: 1.15,
            }}
          >
            Terbatas, disengaja, dan bisa ditelusuri.
          </h2>
          <p
            style={{
              fontSize: 14.5,
              color: "var(--ink-2)",
              lineHeight: 1.55,
              marginTop: 14,
            }}
          >
            Kami tidak mengindeks internet. Kami tidak mengindeks UpToDate. Hanya
            dokumen yang Kemenkes adopsi secara resmi — itulah yang memberi
            pertanggungjawaban hukum pada setiap sitasi.
          </p>
        </div>

        <div style={{ border: "1px solid var(--rule)", background: "var(--paper-2)" }}>
          <div
            style={{
              display: "grid",
              gridTemplateColumns: "repeat(auto-fit, minmax(120px, 1fr))",
              borderBottom: "1px solid var(--rule)",
            }}
          >
            <Stat v="80" l="Dokumen" />
            <Stat v="8.864" l="Potongan terindeks" />
            <Stat v="12.407" l="Halaman" />
            <Stat v="3" l="Jenis sumber" />
          </div>
          <div style={{ padding: 20 }}>
            <div className="label" style={{ marginBottom: 12 }}>
              Komposisi sumber
            </div>
            <SourceBar />
            <div
              style={{
                display: "flex",
                gap: 18,
                marginTop: 12,
                fontSize: 12,
                flexWrap: "wrap",
              }}
            >
              <LegendDot color="var(--navy)" label="PPK FKTP · 47" />
              <LegendDot color="var(--teal)" label="PNPK · 21" />
              <LegendDot color="var(--oxblood)" label="Kepmenkes · 12" />
            </div>
          </div>
        </div>
      </div>
    </section>
  );
}

function Stat({ v, l }: { v: string; l: string }) {
  return (
    <div style={{ padding: "18px 16px", borderRight: "1px solid var(--rule)" }}>
      <div
        className="display"
        style={{
          fontSize: 28,
          fontWeight: 500,
          color: "var(--ink)",
          letterSpacing: "-0.02em",
        }}
      >
        {v}
      </div>
      <div
        className="mono"
        style={{
          fontSize: 10.5,
          color: "var(--ink-3)",
          textTransform: "uppercase",
          letterSpacing: "0.1em",
          marginTop: 2,
        }}
      >
        {l}
      </div>
    </div>
  );
}

function SourceBar() {
  return (
    <div style={{ display: "flex", height: 10, borderRadius: 0, overflow: "hidden" }}>
      <div style={{ width: "58.75%", background: "var(--navy)" }} />
      <div style={{ width: "26.25%", background: "var(--teal)" }} />
      <div style={{ width: "15%", background: "var(--oxblood)" }} />
    </div>
  );
}

function LegendDot({ color, label }: { color: string; label: string }) {
  return (
    <div style={{ display: "flex", alignItems: "center", gap: 7, color: "var(--ink-2)" }}>
      <span style={{ width: 9, height: 9, background: color, borderRadius: 0 }} />
      <span className="mono" style={{ fontSize: 11 }}>
        {label}
      </span>
    </div>
  );
}

function LandingCTA() {
  return (
    <section
      style={{
        padding: "64px clamp(20px, 5vw, 56px)",
        maxWidth: 1280,
        margin: "0 auto",
        borderTop: "1px solid var(--rule)",
      }}
    >
      <div
        style={{
          background: "var(--ink)",
          color: "var(--paper)",
          padding: "clamp(32px, 5vw, 48px)",
          display: "grid",
          gridTemplateColumns: "minmax(0, 1.5fr) minmax(0, 1fr)",
          gap: 32,
          alignItems: "center",
          borderRadius: 2,
          position: "relative",
          overflow: "hidden",
        }}
      >
        <div>
          <div
            className="mono"
            style={{
              fontSize: 10.5,
              letterSpacing: "0.14em",
              color: "var(--paper-3)",
              opacity: 0.7,
              marginBottom: 10,
            }}
          >
            § 05 — MULAI
          </div>
          <h2
            className="display"
            style={{
              fontSize: "clamp(24px, 3.4vw, 36px)",
              margin: 0,
              fontWeight: 500,
              letterSpacing: "-0.02em",
              lineHeight: 1.12,
            }}
          >
            Buka aplikasi.{" "}
            <em style={{ color: "color-mix(in oklch, var(--teal) 80%, white)" }}>
              Tanya dalam Bahasa Indonesia.
            </em>
          </h2>
          <p
            style={{
              fontSize: 14,
              color: "var(--paper-3)",
              opacity: 0.85,
              marginTop: 14,
              lineHeight: 1.55,
              maxWidth: 520,
            }}
          >
            Tanpa pendaftaran, tanpa biaya. Seluruh jawaban tetap bersifat
            referensial — Anamnesa adalah alat rujukan klinis, bukan alat
            diagnosis.
          </p>
        </div>
        <div style={{ display: "flex", flexDirection: "column", gap: 10 }}>
          <Link
            href="/chat"
            className="btn btn-primary"
            style={{
              background: "var(--paper)",
              color: "var(--ink)",
              padding: "14px 18px",
              fontSize: 14,
              justifyContent: "center",
            }}
          >
            Masuk ke Mode Agen →
          </Link>
          <Link
            href="/guideline"
            className="btn btn-ghost"
            style={{
              borderColor: "var(--ink-3)",
              color: "var(--paper)",
              padding: "14px 18px",
              fontSize: 14,
              justifyContent: "center",
            }}
          >
            Jelajahi 80 dokumen
          </Link>
        </div>
      </div>
    </section>
  );
}

function LandingFooter() {
  return (
    <footer
      style={{
        borderTop: "1px solid var(--rule)",
        padding: "36px clamp(20px, 5vw, 56px) 48px",
        maxWidth: 1280,
        margin: "0 auto",
      }}
    >
      <div
        style={{
          display: "grid",
          gridTemplateColumns: "repeat(auto-fit, minmax(160px, 1fr))",
          gap: 32,
        }}
      >
        <div style={{ gridColumn: "span 2", minWidth: 0 }}>
          <Wordmark size={15} />
          <p
            style={{
              fontSize: 12.5,
              color: "var(--ink-3)",
              marginTop: 12,
              maxWidth: 400,
              lineHeight: 1.55,
            }}
          >
            Anamnesa adalah alat rujukan klinis, <strong>bukan alat diagnosis</strong>. Keputusan tata laksana tetap menjadi kewajiban klinisi yang bertanggung jawab.
          </p>
        </div>
        <FooterCol t="Aplikasi" items={["Mode Agen", "Pencarian", "Pustaka Guideline", "Riwayat"]} />
        <FooterCol t="Tentang" items={["Metodologi", "Dasar hukum", "Kontributor", "Changelog"]} />
        <FooterCol t="Kontak" items={["Lapor bug", "Kirim guideline", "Umpan balik klinis"]} />
      </div>
      <div
        style={{
          marginTop: 32,
          paddingTop: 20,
          borderTop: "1px solid var(--rule)",
          display: "flex",
          justifyContent: "space-between",
          fontSize: 11.5,
          color: "var(--ink-3)",
          flexWrap: "wrap",
          gap: 10,
        }}
        className="mono"
      >
        <span>© 2026 Anamnesa · UU 28/2014 Ps. 42 · public domain corpus</span>
        <span>anamnesa.kudaliar.id</span>
      </div>
    </footer>
  );
}

function FooterCol({ t, items }: { t: string; items: string[] }) {
  return (
    <div>
      <div className="label" style={{ marginBottom: 10 }}>
        {t}
      </div>
      <ul style={{ listStyle: "none", padding: 0, margin: 0, display: "flex", flexDirection: "column", gap: 7 }}>
        {items.map((i) => (
          <li key={i} style={{ fontSize: 13, color: "var(--ink-2)" }}>
            {i}
          </li>
        ))}
      </ul>
    </div>
  );
}
