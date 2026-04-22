"use client";

import { useEffect, useState } from "react";

/**
 * Civic-tech masthead — like pasal.id's header block. A bold wordmark
 * left, corpus stats right, descriptive subtitle, thin bottom rule.
 */
export function Masthead() {
  const [info, setInfo] = useState<{ docs: number; embedder: string } | null>(
    null,
  );

  useEffect(() => {
    const base = process.env.NEXT_PUBLIC_ANAMNESA_API ?? "";
    fetch(`${base.replace(/\/$/, "")}/api/health`)
      .then((r) => (r.ok ? r.json() : null))
      .then((d) => d && setInfo({ docs: d.docs_indexed, embedder: d.embedder }))
      .catch(() => {});
  }, []);

  return (
    <header className="pt-8 pb-5 border-b border-paper-edge">
      <div className="flex items-end justify-between gap-6 flex-wrap">
        <div>
          <h1 className="font-display text-display-xl text-ink leading-none">
            Anamnesa
          </h1>
          <p className="mt-2 text-body text-ink-mid max-w-[58ch]">
            Pencarian pedoman klinis Indonesia berbasis agen. Setiap
            jawaban dikutip langsung ke pedoman asli, dengan bendera
            keberlakuan.
          </p>
        </div>
        <div className="flex flex-col items-end gap-2">
          <div className="flex items-center gap-2 text-caption font-mono uppercase tracking-editorial text-ink-faint">
            <span>PS1</span>
            <span className="w-1 h-1 rounded-full bg-ink-ghost" />
            <span>Hakathon Opus 4.7</span>
            <span className="w-1 h-1 rounded-full bg-ink-ghost" />
            <span>21–27 Apr 2026</span>
          </div>
          {info && (
            <div className="flex items-center gap-2 text-caption font-mono text-ink-faint">
              <span className="source-pill">{info.embedder}</span>
              <span>{info.docs} dokumen terindeks</span>
            </div>
          )}
        </div>
      </div>
    </header>
  );
}
