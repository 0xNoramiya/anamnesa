import Link from "next/link";
import { TopBar } from "@/components/shell/TopBar";

export const metadata = { title: "Agent Track · Anamnesa" };

export default function AgentTrackPage() {
  return (
    <>
      <TopBar
        title="Agent Track"
        subtitle="// jejak eksekusi · per fase · per tool"
      />
      <div className="mx-auto max-w-[960px] px-6 lg:px-10 py-10 md:py-14">
        <div
          style={{
            padding: "40px 28px",
            border: "1px dashed var(--rule)",
            background: "var(--paper-2)",
            borderRadius: 2,
            color: "var(--ink-2)",
            lineHeight: 1.6,
          }}
        >
          <div
            className="mono"
            style={{
              fontSize: 10.5,
              color: "var(--oxblood)",
              letterSpacing: "0.14em",
              marginBottom: 10,
            }}
          >
            § LIVE TRACE AT CHAT
          </div>
          <h2
            className="display"
            style={{
              fontSize: 26,
              margin: 0,
              fontWeight: 500,
              letterSpacing: "-0.01em",
            }}
          >
            Jejak eksekusi tampil langsung di Mode Agen.
          </h2>
          <p style={{ marginTop: 12, fontSize: 14, maxWidth: 580 }}>
            Setiap kueri di <strong>Chat</strong> memancarkan peristiwa per
            agen (normalizer → retriever → drafter → verifier) ke panel
            sebelah kanan. Rekaman lintas-sesi untuk ditinjau belakangan akan
            tersedia di rilis berikutnya.
          </p>
          <p style={{ marginTop: 14, fontSize: 13, color: "var(--ink-3)" }}>
            Saat ini jejak disimpan per-query di memori server; tutup tab dan
            jejaknya hilang. Untuk pengembangan:{" "}
            <code>GET /api/stream/&lt;query_id&gt;</code> mengalirkan peristiwa
            SSE mentah.
          </p>
          <div style={{ marginTop: 22, display: "flex", gap: 10 }}>
            <Link
              href="/chat"
              className="btn btn-primary"
              style={{ padding: "8px 14px", fontSize: 13 }}
            >
              Ke Chat →
            </Link>
            <a
              href="https://github.com/0xNoramiya/anamnesa"
              target="_blank"
              rel="noreferrer"
              className="btn btn-ghost"
              style={{ padding: "8px 14px", fontSize: 13 }}
            >
              Lihat kode sumber ↗
            </a>
          </div>
        </div>
      </div>
    </>
  );
}
