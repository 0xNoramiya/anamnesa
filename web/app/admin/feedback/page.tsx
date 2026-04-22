"use client";

import { useEffect, useState } from "react";

const API_BASE = process.env.NEXT_PUBLIC_ANAMNESA_API ?? "";

interface Entry {
  query_text: string;
  rating: "up" | "down";
  note: string | null;
  created_at: number;             // epoch seconds
}

interface Stats {
  total: number;
  up: number;
  down: number;
  recent: Entry[];
}

const REFRESH_MS = 30_000;

export default function FeedbackAdminPage() {
  const [stats, setStats] = useState<Stats | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [refreshedAt, setRefreshedAt] = useState<number | null>(null);

  const load = async () => {
    try {
      const r = await fetch(
        `${API_BASE.replace(/\/$/, "")}/api/feedback/stats`,
        { cache: "no-store" },
      );
      if (!r.ok) throw new Error(`HTTP ${r.status}`);
      const j = (await r.json()) as Stats;
      setStats(j);
      setError(null);
      setRefreshedAt(Date.now());
    } catch (e) {
      setError((e as Error).message);
    }
  };

  useEffect(() => {
    void load();
    const h = window.setInterval(load, REFRESH_MS);
    return () => window.clearInterval(h);
  }, []);

  const satisfaction = stats && stats.total > 0 ? (stats.up / stats.total) * 100 : null;

  return (
    <main className="min-h-screen">
      <div className="mx-auto max-w-[1100px] px-6 lg:px-10 py-10">
        <header className="mb-8">
          <p className="chapter-mark text-ink-faint">Anamnesa · Admin</p>
          <h1 className="text-3xl font-semibold text-ink mt-1">
            Umpan Balik Pengguna
          </h1>
          <p className="mt-2 text-body text-ink-mid max-w-[58ch] leading-relaxed">
            Sinyal thumbs-up / thumbs-down dari halaman jawaban Mode Agen.
            Setiap entri tersimpan di SQLite (<code className="font-mono text-caption">catalog/cache/feedback.db</code>);
            dirender langsung dari <code className="font-mono text-caption">/api/feedback/stats</code>.
          </p>
        </header>

        <section className="grid grid-cols-2 md:grid-cols-4 gap-3 mb-8">
          <MetricCard label="Total entri" value={stats?.total ?? "…"} />
          <MetricCard
            label="Membantu"
            value={stats?.up ?? "…"}
            accent="civic"
          />
          <MetricCard
            label="Tidak membantu"
            value={stats?.down ?? "…"}
            accent="oxblood"
          />
          <MetricCard
            label="Persentase positif"
            value={
              satisfaction !== null
                ? `${satisfaction.toFixed(0)}%`
                : "—"
            }
          />
        </section>

        {error && (
          <div className="mb-6 bg-oxblood/5 border border-oxblood/20 rounded-lg p-4">
            <div className="chapter-mark text-oxblood mb-1">Gagal muat</div>
            <p className="text-body text-ink-mid">{error}</p>
          </div>
        )}

        <section>
          <div className="flex items-center gap-3 mb-3">
            <h2 className="chapter-mark">Riwayat Terbaru</h2>
            <span className="flex-1 h-px bg-paper-edge" />
            <span className="text-caption text-ink-faint font-mono">
              {refreshedAt ? `diperbarui ${timeAgo(Date.now() - refreshedAt)}` : "memuat…"}
            </span>
          </div>

          {stats && stats.recent.length === 0 && (
            <div className="py-10 text-center border border-dashed border-paper-edge rounded-lg">
              <p className="text-body-lg text-ink-mid">Belum ada entri.</p>
              <p className="mt-1 text-caption text-ink-faint">
                Tekan 👍 / 👎 di halaman jawaban Mode Agen untuk mengujinya.
              </p>
            </div>
          )}

          {stats && stats.recent.length > 0 && (
            <ol className="divide-y divide-paper-edge border border-paper-edge rounded-lg overflow-hidden bg-white">
              {stats.recent.map((e, i) => (
                <FeedbackRow key={i} entry={e} />
              ))}
            </ol>
          )}
        </section>

        <footer className="mt-10 pt-5 border-t border-paper-edge">
          <p className="text-caption text-ink-faint leading-relaxed max-w-[62ch]">
            Data ini bukan PII — tidak ada sesi, cookie, atau identitas
            pengguna yang disimpan. Hanya teks pertanyaan klinis (≤2000 char),
            rating, dan catatan opsional. Diperbarui otomatis setiap 30 detik.
          </p>
        </footer>
      </div>
    </main>
  );
}

function MetricCard({
  label,
  value,
  accent,
}: {
  label: string;
  value: number | string;
  accent?: "civic" | "oxblood";
}) {
  const tone =
    accent === "civic"
      ? "text-civic"
      : accent === "oxblood"
        ? "text-oxblood"
        : "text-ink";
  return (
    <div className="bg-white border border-paper-edge rounded-lg p-4">
      <p className="text-caption font-mono uppercase tracking-editorial text-ink-faint">
        {label}
      </p>
      <p className={`mt-1 font-semibold text-2xl tabular-nums ${tone}`}>{value}</p>
    </div>
  );
}

function FeedbackRow({ entry }: { entry: Entry }) {
  const age = timeAgo(Date.now() - entry.created_at * 1000);
  const isUp = entry.rating === "up";
  return (
    <li className="flex items-start gap-3 px-4 py-3 hover:bg-paper-deep/40 transition-colors">
      <span
        className={`shrink-0 inline-flex items-center justify-center w-7 h-7 rounded-md
                     ${isUp ? "bg-civic/10 text-civic" : "bg-oxblood/10 text-oxblood"}`}
        aria-label={isUp ? "positif" : "negatif"}
      >
        {isUp ? (
          <svg width="14" height="14" viewBox="0 0 24 24" fill="currentColor">
            <path d="M7 10v11h13.5c1 0 1.9-.7 2.1-1.7l2-9c.3-1.4-.8-2.8-2.2-2.8H15l1.4-4.5c.3-1-.5-2-1.5-2-.6 0-1.2.3-1.5.8L7 10z" />
          </svg>
        ) : (
          <svg width="14" height="14" viewBox="0 0 24 24" fill="currentColor">
            <path d="M17 14V3H3.5c-1 0-1.9.7-2.1 1.7l-2 9C-.9 15.1.2 16.5 1.6 16.5H9l-1.4 4.5c-.3 1 .5 2 1.5 2 .6 0 1.2-.3 1.5-.8L17 14z" />
          </svg>
        )}
      </span>
      <div className="flex-1 min-w-0">
        <p className="text-body text-ink leading-relaxed break-words">
          {entry.query_text}
        </p>
        {entry.note && (
          <blockquote className="mt-1.5 pl-3 border-l-2 border-paper-edge text-body text-ink-mid leading-relaxed">
            {entry.note}
          </blockquote>
        )}
        <p className="mt-1 text-caption font-mono text-ink-faint">{age}</p>
      </div>
    </li>
  );
}

function timeAgo(ms: number): string {
  const s = Math.floor(ms / 1000);
  if (s < 10) return "baru saja";
  if (s < 60) return `${s} detik lalu`;
  const m = Math.floor(s / 60);
  if (m < 60) return `${m} menit lalu`;
  const h = Math.floor(m / 60);
  if (h < 24) return `${h} jam lalu`;
  const d = Math.floor(h / 24);
  return `${d} hari lalu`;
}
