"use client";

import { useEffect, useState } from "react";

/**
 * Editorial masthead — the title block at the top of every page.
 * Pays homage to Kemenkes document title blocks: display serif wordmark,
 * a small-caps subtitle, a ruled line with issue metadata, and a slim
 * row of corpus stats pulled from /api/manifest.
 */
export function Masthead() {
  const [info, setInfo] = useState<{ docs: number; embedder: string } | null>(
    null,
  );

  useEffect(() => {
    fetch("/api/health")
      .then((r) => r.ok ? r.json() : null)
      .then((d) => d && setInfo({ docs: d.docs_indexed, embedder: d.embedder }))
      .catch(() => {});
  }, []);

  return (
    <header className="border-b border-ink pt-10 pb-4">
      <div className="flex items-baseline justify-between gap-6 flex-wrap">
        <div>
          <div className="chapter-mark">
            Referensi Pedoman Klinis Indonesia · PS1
          </div>
          <h1 className="font-display text-display-xl text-ink mt-1">
            Anamnesa
          </h1>
        </div>
        <div className="text-right font-mono text-caption text-ink-faint uppercase tracking-editorial leading-snug">
          <div>Edisi Hakathon</div>
          <div>21–27 April 2026</div>
          <div>Banjarmasin, Kalsel</div>
        </div>
      </div>

      <div className="mt-4 flex items-center justify-between gap-4 flex-wrap text-caption text-ink-faint">
        <p className="italic max-w-[62ch]">
          Alat retrieval pedoman klinis berbasis agen — Haiku 4.5 + Opus 4.7
          via Anthropic. Korpus: UU No. 28/2014 Pasal 42 (domain publik).
        </p>
        {info && (
          <div className="font-mono text-[0.72rem] uppercase tracking-editorial">
            <span>{info.docs} dokumen</span>
            <span className="mx-2">·</span>
            <span>embedder: {info.embedder}</span>
          </div>
        )}
      </div>
    </header>
  );
}
