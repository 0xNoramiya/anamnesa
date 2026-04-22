import { TopBar } from "@/components/shell/TopBar";

export const metadata = { title: "Favorit · Anamnesa" };

export default function FavoritPage() {
  return (
    <>
      <TopBar
        title="Favorit"
        subtitle="// pintasan pribadi · jawaban · kutipan · dokumen"
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
            § SEGERA HADIR
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
            Pintasan pribadi akan tersedia di rilis berikutnya.
          </h2>
          <p style={{ marginTop: 12, fontSize: 14, maxWidth: 560 }}>
            Tandai jawaban, kutipan referensi, atau dokumen guideline dengan{" "}
            <strong>★</strong> untuk menyimpannya di sini — tersimpan di{" "}
            <code>localStorage</code> peramban Anda, tanpa server.
          </p>
          <p
            className="mono"
            style={{
              marginTop: 16,
              fontSize: 11,
              color: "var(--ink-3)",
              letterSpacing: "0.06em",
            }}
          >
            Sementara itu, gunakan <strong>Riwayat</strong> untuk kembali ke 20
            kueri terakhir, atau <strong>Salin kutipan</strong> pada kartu
            referensi untuk menyalin potongan teks ke catatan Anda.
          </p>
        </div>
      </div>
    </>
  );
}
