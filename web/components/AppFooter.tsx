"use client";

import { useEffect, useState } from "react";

const API_BASE = process.env.NEXT_PUBLIC_ANAMNESA_API ?? "";

interface Meta {
  version: { sha: string; date: string; subject?: string };
  corpus: {
    docs: number;
    chunks: number;
    year_min: number | null;
    year_max: number | null;
    embedder: string;
  };
  cache: { count: number; oldest_age_s: number | null; newest_age_s: number | null } | null;
  legal_basis: string;
}

/**
 * Compact footer rendered below every page. Pulls from /api/meta so
 * judges (and curious doctors) can see what version + corpus they're
 * actually running against. Keyed to the commit SHA — if a redeploy
 * ships, the footer updates on next page-load.
 */
export function AppFooter() {
  const [meta, setMeta] = useState<Meta | null>(null);

  useEffect(() => {
    const ac = new AbortController();
    fetch(`${API_BASE.replace(/\/$/, "")}/api/meta`, { signal: ac.signal })
      .then((r) => (r.ok ? r.json() : null))
      .then((m) => setMeta(m))
      .catch(() => {
        // Network hiccup or /api/meta not deployed yet — fall back to
        // no-footer rather than rendering an error box.
      });
    return () => ac.abort();
  }, []);

  if (!meta) return null;

  const yearRange =
    meta.corpus.year_min && meta.corpus.year_max
      ? `${meta.corpus.year_min}–${meta.corpus.year_max}`
      : "";

  const shaShort = (meta.version.sha ?? "dev").slice(0, 7);

  return (
    <footer className="mt-8 border-t border-paper-edge">
      <div className="mx-auto max-w-[1440px] px-6 lg:px-10 py-5">
        <div className="flex items-center gap-x-5 gap-y-2 flex-wrap text-caption font-mono text-ink-faint tabular-nums">
          <MetaCell label="Korpus">
            {meta.corpus.docs} dokumen · {meta.corpus.chunks.toLocaleString()} potongan{yearRange ? ` · ${yearRange}` : ""}
          </MetaCell>
          <Dot />
          <MetaCell label="Embedder">{meta.corpus.embedder}</MetaCell>
          {meta.cache && (
            <>
              <Dot />
              <MetaCell label="Cache">
                {meta.cache.count} entri
                {meta.cache.count > 0 && meta.cache.newest_age_s != null && (
                  <> · {formatAge(meta.cache.newest_age_s)} lalu</>
                )}
              </MetaCell>
            </>
          )}
          <Dot />
          <MetaCell label="Versi">
            <a
              href={`https://github.com/0xNoramiya/anamnesa/commit/${meta.version.sha}`}
              target="_blank"
              rel="noreferrer"
              className="text-ink-mid hover:text-civic transition-colors"
              title={meta.version.subject ?? meta.version.sha}
            >
              {shaShort}
            </a>
          </MetaCell>
        </div>
        <p className="mt-3 text-caption text-ink-faint leading-relaxed max-w-[64ch]">
          Korpus adalah pedoman Indonesia domain publik berdasarkan{" "}
          <span className="text-ink-mid font-semibold">{meta.legal_basis}</span>{" "}
          (Hak Cipta). Anamnesa adalah alat rujukan klinis, bukan alat diagnosis
          atau rekomendasi terapi untuk pasien individual. Keputusan klinis tetap
          menjadi tanggung jawab dokter.
        </p>
      </div>
    </footer>
  );
}

function MetaCell({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <span className="inline-flex items-center gap-1.5">
      <span className="uppercase tracking-editorial text-[0.68rem] text-ink-ghost">{label}</span>
      <span className="text-ink-mid">{children}</span>
    </span>
  );
}

function Dot() {
  return <span className="text-ink-ghost select-none">·</span>;
}

function formatAge(s: number): string {
  if (s < 60) return "baru saja";
  if (s < 3600) return `${Math.round(s / 60)} menit`;
  if (s < 86400) return `${Math.round(s / 3600)} jam`;
  return `${Math.round(s / 86400)} hari`;
}
