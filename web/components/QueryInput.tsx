"use client";

import { useEffect, useRef, useState, type FormEvent, type KeyboardEvent } from "react";
import type { StreamStatus } from "@/lib/useQueryStream";

interface Props {
  onSubmit: (query: string) => void;
  status: StreamStatus;
  /** Follow-up mode: different label + placeholder, examples hidden. */
  followUp?: boolean;
}

const EXAMPLES = [
  "Bayi baru lahir tidak menangis, apnea, HR <100. Langkah resusitasi awal dalam 60 detik pertama?",
  "Pasien TB paru dewasa baru BTA positif. Rejimen OAT lini pertama dan durasi?",
  "Luka bakar derajat II 30% TBSA dewasa. Cairan resusitasi 24 jam pertama?",
];

const INPUT_TAGS = new Set(["INPUT", "TEXTAREA", "SELECT"]);

export function QueryInput({ onSubmit, status, followUp = false }: Props) {
  const [value, setValue] = useState("");
  const busy = status === "submitting" || status === "streaming";
  const textareaRef = useRef<HTMLTextAreaElement | null>(null);

  const label = followUp ? "Pertanyaan lanjutan" : "Pertanyaan Klinis";
  const placeholder = followUp
    ? "Ajukan pertanyaan lanjutan — Anamnesa ingat percakapan ini. Contoh: “dan kalau pasien anak?”, “berapa dosisnya?”, “alternatifnya apa?”"
    : "Tulis pertanyaan klinis dalam Bahasa Indonesia. Anamnesa mengutip pedoman Indonesia (Pasal 42 UU 28/2014 — domain publik).";

  // Global shortcut: `/` focuses the query input (skipped while typing
  // elsewhere). Mirrors GitHub / Linear / Notion and costs nothing for
  // users who don't know it exists.
  useEffect(() => {
    const onKey = (e: globalThis.KeyboardEvent) => {
      if (e.key !== "/") return;
      if (e.defaultPrevented || e.metaKey || e.ctrlKey || e.altKey) return;
      const target = e.target as HTMLElement | null;
      if (!target) return;
      const tag = target.tagName;
      if (INPUT_TAGS.has(tag) || target.isContentEditable) return;
      e.preventDefault();
      textareaRef.current?.focus();
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, []);

  const handleSubmit = (e: FormEvent) => {
    e.preventDefault();
    const q = value.trim();
    if (!q || busy) return;
    onSubmit(q);
  };

  const handleKeyDown = (e: KeyboardEvent<HTMLTextAreaElement>) => {
    // Cmd/Ctrl+Enter submits even when the submit button isn't focused.
    if (e.key === "Enter" && (e.metaKey || e.ctrlKey)) {
      e.preventDefault();
      const q = value.trim();
      if (!q || busy) return;
      onSubmit(q);
    }
  };

  return (
    <div>
      <form onSubmit={handleSubmit}>
        <label htmlFor="query" className="chapter-mark block mb-2">
          {label}
        </label>
        <div className="bg-white border border-paper-edge rounded-lg shadow-card focus-within:shadow-card-hover transition-shadow">
          <textarea
            id="query"
            ref={textareaRef}
            value={value}
            onChange={(e) => setValue(e.target.value)}
            onKeyDown={handleKeyDown}
            disabled={busy}
            rows={3}
            placeholder={placeholder}
            className="w-full resize-none bg-transparent border-0 focus:outline-none
                       px-4 py-3 text-body-lg leading-relaxed text-ink
                       placeholder:text-ink-ghost"
          />
          <div className="flex items-center justify-between px-4 py-2 border-t border-paper-edge">
            <div className="text-caption text-ink-faint flex items-center gap-2">
              {value.length > 0 ? (
                <>{value.length} karakter</>
              ) : (
                <>
                  Tekan <Kbd>/</Kbd> untuk fokus · <Kbd>⌘</Kbd><Kbd>↵</Kbd> untuk kirim
                </>
              )}
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

      {!busy && status !== "done" && !followUp && (
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

function Kbd({ children }: { children: React.ReactNode }) {
  return (
    <kbd
      className="inline-flex items-center justify-center min-w-[1.3em] h-[1.3em]
                 px-1 rounded border border-paper-edge bg-white
                 font-mono text-[0.7rem] text-ink-mid leading-none"
    >
      {children}
    </kbd>
  );
}
