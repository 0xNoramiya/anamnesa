"use client";

import { useState, type FormEvent } from "react";
import type { StreamStatus } from "@/lib/useQueryStream";

interface Props {
  onSubmit: (query: string) => void;
  status: StreamStatus;
}

const EXAMPLES = [
  "Bayi baru lahir tidak menangis, apnea, HR <100. Langkah resusitasi awal dalam 60 detik pertama?",
  "Pasien TB paru dewasa baru BTA positif. Rejimen OAT lini pertama dan durasi?",
  "Luka bakar derajat II 30% TBSA dewasa. Cairan resusitasi 24 jam pertama?",
];

export function QueryInput({ onSubmit, status }: Props) {
  const [value, setValue] = useState("");
  const busy = status === "submitting" || status === "streaming";

  const handleSubmit = (e: FormEvent) => {
    e.preventDefault();
    const q = value.trim();
    if (!q || busy) return;
    onSubmit(q);
  };

  return (
    <div>
      <form onSubmit={handleSubmit} className="relative">
        <label
          htmlFor="query"
          className="chapter-mark block mb-2"
        >
          Pertanyaan Klinis · Query
        </label>
        <div className="relative">
          <textarea
            id="query"
            value={value}
            onChange={(e) => setValue(e.target.value)}
            disabled={busy}
            rows={3}
            placeholder="Tulis pertanyaan klinis dalam Bahasa Indonesia — Anamnesa hanya mengutip pedoman Indonesia berdasarkan Pasal 42 UU 28/2014."
            className="w-full resize-none bg-paper-deep/40 border border-paper-edge
                       focus:border-ink focus:outline-none focus:bg-paper
                       px-5 py-4 text-body-lg leading-relaxed
                       placeholder:text-ink-ghost placeholder:italic
                       transition-colors"
          />
          <button
            type="submit"
            disabled={busy || !value.trim()}
            className="absolute bottom-3 right-3 px-4 py-2
                       bg-ink text-paper font-mono uppercase
                       text-caption tracking-editorial
                       disabled:opacity-30 disabled:cursor-not-allowed
                       enabled:hover:bg-oxblood enabled:active:bg-oxblood-deep
                       transition-colors"
          >
            {busy ? "…" : "Kirim"}
          </button>
        </div>
      </form>

      {!busy && status !== "done" && (
        <div className="mt-5">
          <div className="chapter-mark mb-2">Contoh skenario</div>
          <ul className="space-y-1.5">
            {EXAMPLES.map((ex, i) => (
              <li key={i}>
                <button
                  type="button"
                  onClick={() => setValue(ex)}
                  className="w-full text-left text-body text-ink-mid hover:text-ink
                             py-1.5 px-3 -ml-3 transition-colors
                             border-l-2 border-transparent hover:border-oxblood"
                >
                  {ex}
                </button>
              </li>
            ))}
          </ul>
        </div>
      )}
    </div>
  );
}
