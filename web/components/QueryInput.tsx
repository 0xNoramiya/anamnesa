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
      <form onSubmit={handleSubmit}>
        <label htmlFor="query" className="chapter-mark block mb-2">
          Pertanyaan Klinis
        </label>
        <div className="bg-white border border-paper-edge rounded-lg shadow-card focus-within:shadow-card-hover transition-shadow">
          <textarea
            id="query"
            value={value}
            onChange={(e) => setValue(e.target.value)}
            disabled={busy}
            rows={3}
            placeholder="Tulis pertanyaan klinis dalam Bahasa Indonesia. Anamnesa mengutip pedoman Indonesia (Pasal 42 UU 28/2014 — domain publik)."
            className="w-full resize-none bg-transparent border-0 focus:outline-none
                       px-4 py-3 text-body-lg leading-relaxed text-ink
                       placeholder:text-ink-ghost"
          />
          <div className="flex items-center justify-between px-4 py-2 border-t border-paper-edge">
            <div className="text-caption text-ink-faint">
              {value.length > 0 ? `${value.length} karakter` : "Tekan Cmd+Enter untuk kirim"}
            </div>
            <button
              type="submit"
              disabled={busy || !value.trim()}
              className="px-4 py-1.5 rounded-md bg-civic text-white
                         font-medium text-sm
                         disabled:opacity-40 disabled:cursor-not-allowed
                         enabled:hover:bg-civic-hover transition-colors"
            >
              {status === "submitting" ? "Memulai…" : status === "streaming" ? "Berjalan…" : "Kirim"}
            </button>
          </div>
        </div>
      </form>

      {!busy && status !== "done" && (
        <div className="mt-6">
          <div className="chapter-mark mb-2">Contoh skenario</div>
          <ul className="space-y-1.5">
            {EXAMPLES.map((ex, i) => (
              <li key={i}>
                <button
                  type="button"
                  onClick={() => setValue(ex)}
                  className="w-full text-left text-body text-ink-mid hover:text-civic
                             py-1.5 px-3 -ml-3 rounded-md transition-colors
                             hover:bg-civic/5"
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
