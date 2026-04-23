import Link from "next/link";
import { Wordmark } from "@/components/shell/Logo";
import { CurrencyChip } from "@/components/shell/CurrencyChip";

/**
 * Landing page — tighter, professional rewrite:
 * - No fake document chrome (§ section markers), no version footer
 * - Hero H1 truncated, single-sentence subhead
 * - ONE concrete demo, not three
 * - Three feature bullets replace the audience + three-demo blocks
 * - Legal basis + CTA band stay; footer simplified
 * All columns stack on mobile; hero scales down via clamp().
 */
export function Landing() {
  return (
    <div style={{ background: "var(--paper)", color: "var(--ink)", minHeight: "100vh" }}>
      <LandingHeader />
      <LandingHero />
      <LandingFeatures />
      <LandingDemo />
      <LandingLegal />
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
        padding: "12px clamp(18px, 5vw, 56px)",
        display: "flex",
        alignItems: "center",
        gap: 14,
      }}
    >
      <Wordmark size={15} />
      <div style={{ flex: 1 }} />
      <Link
        href="/chat"
        className="btn btn-primary"
        style={{ padding: "8px 14px", fontSize: 13 }}
      >
        Buka aplikasi →
      </Link>
    </div>
  );
}

function LandingHero() {
  return (
    <section
      style={{
        padding: "clamp(48px, 9vw, 96px) clamp(20px, 5vw, 56px) clamp(32px, 6vw, 56px)",
        maxWidth: 1200,
        margin: "0 auto",
      }}
    >
      <h1
        className="display"
        style={{
          fontSize: "clamp(34px, 6.5vw, 64px)",
          lineHeight: 1.05,
          margin: 0,
          fontWeight: 500,
          letterSpacing: "-0.025em",
          color: "var(--ink)",
          fontVariationSettings: "'opsz' 60, 'SOFT' 30",
          maxWidth: 900,
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
          fontSize: "clamp(16px, 2.2vw, 19px)",
          lineHeight: 1.55,
          marginTop: 22,
          color: "var(--ink-2)",
          maxWidth: 640,
          fontWeight: 400,
        }}
      >
        Tanya dalam Bahasa Indonesia. Setiap jawaban mengutip halaman
        spesifik dari PPK FKTP, PNPK, atau Kepmenkes. Bila korpus tidak
        memuat jawabannya, kami menolak dengan jujur.
      </p>

      <div
        style={{
          display: "flex",
          gap: 10,
          marginTop: 28,
          alignItems: "center",
          flexWrap: "wrap",
        }}
      >
        <Link
          href="/chat"
          className="btn btn-primary"
          style={{ padding: "12px 20px", fontSize: 14 }}
        >
          Buka aplikasi →
        </Link>
        <a
          href="#contoh"
          className="btn btn-ghost"
          style={{ padding: "12px 20px", fontSize: 14 }}
        >
          Lihat contoh
        </a>
      </div>

      <div
        className="mono"
        style={{
          marginTop: 32,
          fontSize: 11.5,
          color: "var(--ink-3)",
          letterSpacing: "0.04em",
          display: "flex",
          flexWrap: "wrap",
          gap: 14,
          alignItems: "center",
        }}
      >
        <span>
          <strong style={{ color: "var(--ink)" }}>80 dokumen</strong> terindeks
        </span>
        <Dot />
        <span>PPK FKTP · PNPK · Kepmenkes</span>
        <Dot />
        <span>UU 28/2014 · domain publik</span>
        <Dot />
        <span>Gratis · tanpa pendaftaran</span>
      </div>
    </section>
  );
}

function Dot() {
  return <span style={{ color: "var(--ink-4)" }}>·</span>;
}

function LandingFeatures() {
  const items = [
    {
      title: "Setiap klaim dikutip",
      body: "Tidak ada paragraf tanpa sumber. Tap angka [N] untuk melompat ke kartu referensi, klik untuk membuka PDF di halaman tepat.",
    },
    {
      title: "Bendera masa berlaku",
      body: "Pedoman yang sudah berusia lebih dari lima tahun ditandai otomatis. Dokumen yang sudah diganti menampilkan versi terbaru.",
    },
    {
      title: "Penolakan, bukan halusinasi",
      body: "Bila korpus tidak memuat jawaban, Anamnesa menolak menjawab dan menampilkan dokumen paling dekat yang sempat ditemukan.",
    },
  ];

  return (
    <section
      style={{
        padding: "clamp(32px, 5vw, 56px) clamp(20px, 5vw, 56px)",
        maxWidth: 1200,
        margin: "0 auto",
        borderTop: "1px solid var(--rule)",
      }}
    >
      <div
        style={{
          display: "grid",
          gridTemplateColumns: "repeat(auto-fit, minmax(240px, 1fr))",
          gap: 20,
        }}
      >
        {items.map((it) => (
          <div
            key={it.title}
            style={{
              padding: "18px 20px",
              background: "var(--paper-2)",
              borderLeft: "2px solid var(--navy)",
            }}
          >
            <h3
              className="display"
              style={{
                fontSize: 18,
                fontWeight: 500,
                margin: 0,
                letterSpacing: "-0.01em",
                color: "var(--ink)",
              }}
            >
              {it.title}
            </h3>
            <p
              style={{
                fontSize: 13.5,
                color: "var(--ink-2)",
                lineHeight: 1.55,
                marginTop: 6,
              }}
            >
              {it.body}
            </p>
          </div>
        ))}
      </div>
    </section>
  );
}

function LandingDemo() {
  return (
    <section
      id="contoh"
      style={{
        padding: "clamp(40px, 6vw, 72px) clamp(20px, 5vw, 56px)",
        maxWidth: 1200,
        margin: "0 auto",
        borderTop: "1px solid var(--rule)",
      }}
    >
      <div style={{ maxWidth: 680, marginBottom: 28 }}>
        <div
          className="mono"
          style={{
            fontSize: 10.5,
            color: "var(--oxblood)",
            letterSpacing: "0.14em",
            marginBottom: 10,
          }}
        >
          CONTOH
        </div>
        <h2
          className="display"
          style={{
            fontSize: "clamp(26px, 3.6vw, 36px)",
            margin: 0,
            fontWeight: 500,
            letterSpacing: "-0.02em",
            lineHeight: 1.15,
            color: "var(--ink)",
          }}
        >
          Satu pertanyaan, satu jawaban tersitasi.
        </h2>
      </div>

      <div
        style={{
          background: "var(--paper-2)",
          border: "1px solid var(--rule)",
          borderRadius: 2,
          boxShadow: "0 1px 0 var(--rule-2), 0 14px 30px -18px rgba(15,27,45,0.14)",
          maxWidth: 820,
        }}
      >
        <div style={{ padding: "18px 22px", borderBottom: "1px solid var(--rule)" }}>
          <div className="label" style={{ marginBottom: 6 }}>
            Pertanyaan
          </div>
          <div style={{ fontSize: 15, color: "var(--ink)", lineHeight: 1.5 }}>
            Pasien dewasa dengan DBD derajat II, trombosit 45.000. Kapan harus
            dirujuk dari Puskesmas?
          </div>
        </div>

        <div style={{ padding: "18px 22px" }}>
          <div className="label" style={{ marginBottom: 8 }}>
            Jawaban
          </div>
          <div
            style={{
              fontSize: 15,
              lineHeight: 1.65,
              color: "var(--ink)",
            }}
          >
            Rujuk bila pasien menunjukkan tanda syok (tekanan nadi ≤ 20 mmHg,
            akral dingin, CRT &gt; 2 detik)<span className="cite">1</span>,
            perdarahan spontan masif<span className="cite">2</span>, atau
            trombosit turun &lt; 100.000 dengan hematokrit meningkat ≥ 20% dari
            baseline<span className="cite">1</span>.
          </div>

          <div
            style={{
              marginTop: 14,
              display: "flex",
              gap: 8,
              flexWrap: "wrap",
              alignItems: "center",
            }}
          >
            <CurrencyChip kind="current" year={2023} />
            <span
              className="mono"
              style={{ fontSize: 10.5, color: "var(--ink-3)" }}
            >
              2 sitasi · PPK FKTP
            </span>
          </div>

          <div
            style={{
              marginTop: 16,
              display: "flex",
              flexDirection: "column",
              gap: 8,
            }}
          >
            <MiniRef
              n={1}
              doc="PPK FKTP 2023 · Demam Berdarah Dengue"
              page="hal. 142"
            />
            <MiniRef
              n={2}
              doc="PPK FKTP 2023 · Demam Berdarah Dengue"
              page="hal. 145"
            />
          </div>
        </div>
      </div>
    </section>
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
          flexShrink: 0,
        }}
      >
        {n}
      </span>
      <span
        style={{
          flex: 1,
          color: "var(--ink)",
          minWidth: 0,
          overflow: "hidden",
          textOverflow: "ellipsis",
          whiteSpace: "nowrap",
        }}
      >
        {doc}
      </span>
      <span
        className="mono"
        style={{ fontSize: 10.5, color: "var(--ink-3)", flexShrink: 0 }}
      >
        {page}
      </span>
    </div>
  );
}

function LandingLegal() {
  return (
    <section
      style={{
        padding: "clamp(32px, 5vw, 56px) clamp(20px, 5vw, 56px)",
        maxWidth: 1200,
        margin: "0 auto",
        borderTop: "1px solid var(--rule)",
      }}
    >
      <div style={{ display: "grid", gap: 20, gridTemplateColumns: "minmax(0, 1fr)" }}>
        <div
          style={{
            padding: "18px 22px",
            borderLeft: "2px solid var(--oxblood)",
            background: "var(--paper-2)",
            maxWidth: 780,
          }}
        >
          <div
            className="mono"
            style={{
              fontSize: 10.5,
              color: "var(--oxblood)",
              letterSpacing: "0.12em",
              marginBottom: 6,
            }}
          >
            DASAR HUKUM
          </div>
          <p style={{ fontSize: 14, color: "var(--ink-2)", lineHeight: 1.6, margin: 0 }}>
            <strong style={{ color: "var(--ink)" }}>
              UU No. 28/2014 Pasal 42
            </strong>{" "}
            menetapkan peraturan perundang-undangan dan keputusan pejabat
            pemerintah sebagai <em>public domain</em>. Anamnesa hanya mengindeks
            dokumen yang sah disebar ulang — PPK FKTP, PNPK, dan Kepmenkes.
          </p>
        </div>
      </div>
    </section>
  );
}

function LandingCTA() {
  return (
    <section
      style={{
        padding: "clamp(40px, 6vw, 72px) clamp(20px, 5vw, 56px)",
        maxWidth: 1200,
        margin: "0 auto",
        borderTop: "1px solid var(--rule)",
      }}
    >
      <div
        style={{
          background: "var(--ink)",
          color: "var(--paper)",
          padding: "clamp(28px, 5vw, 48px)",
          borderRadius: 2,
          display: "grid",
          gridTemplateColumns: "minmax(0, 1.5fr) minmax(0, 1fr)",
          gap: "clamp(20px, 4vw, 40px)",
          alignItems: "center",
        }}
        className="landing-cta-grid"
      >
        <div>
          <h2
            className="display"
            style={{
              fontSize: "clamp(22px, 3.2vw, 32px)",
              margin: 0,
              fontWeight: 500,
              letterSpacing: "-0.02em",
              lineHeight: 1.15,
            }}
          >
            Tanya dalam Bahasa Indonesia.
          </h2>
          <p
            style={{
              fontSize: 14,
              color: "var(--paper-3)",
              opacity: 0.85,
              marginTop: 10,
              lineHeight: 1.55,
              maxWidth: 520,
            }}
          >
            Alat rujukan klinis, bukan alat diagnosis. Keputusan tata laksana
            tetap menjadi kewajiban klinisi.
          </p>
        </div>
        <div style={{ display: "flex", flexDirection: "column", gap: 8 }}>
          <Link
            href="/chat"
            className="btn btn-primary"
            style={{
              background: "var(--paper)",
              color: "var(--ink)",
              padding: "13px 18px",
              fontSize: 14,
              justifyContent: "center",
            }}
          >
            Buka aplikasi →
          </Link>
          <Link
            href="/guideline"
            className="btn btn-ghost"
            style={{
              borderColor: "var(--ink-3)",
              color: "var(--paper)",
              padding: "13px 18px",
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
        padding: "28px clamp(20px, 5vw, 56px) 36px",
        maxWidth: 1200,
        margin: "0 auto",
      }}
    >
      <div
        style={{
          display: "flex",
          justifyContent: "space-between",
          alignItems: "flex-start",
          gap: 20,
          flexWrap: "wrap",
        }}
      >
        <div style={{ maxWidth: 480 }}>
          <Wordmark size={15} />
          <p
            style={{
              fontSize: 12.5,
              color: "var(--ink-3)",
              marginTop: 10,
              lineHeight: 1.55,
            }}
          >
            Alat rujukan klinis, <strong>bukan alat diagnosis</strong>.
            Keputusan tata laksana tetap menjadi kewajiban klinisi.
          </p>
        </div>
        <div
          className="mono"
          style={{
            fontSize: 11,
            color: "var(--ink-3)",
            textAlign: "right",
            lineHeight: 1.6,
          }}
        >
          <div>© 2026 Anamnesa</div>
          <div>UU 28/2014 Ps. 42 · domain publik</div>
          <div>anamnesa.kudaliar.id</div>
        </div>
      </div>
    </footer>
  );
}
