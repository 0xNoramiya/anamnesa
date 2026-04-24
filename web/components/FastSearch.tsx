"use client";

import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import type { Citation } from "@/lib/types";

const API_BASE = process.env.NEXT_PUBLIC_ANAMNESA_API ?? "";

// Search "result" from /api/search — shape matches `Chunk` on the backend
// (fields we care about for the list view + deep-link to PDF).
interface SearchResult {
  doc_id: string;
  page: number;
  section_slug: string;
  section_path: string;
  text: string;
  year: number;
  source_type: string;
  score: number;
}

interface SearchResponse {
  query: string;
  count: number;
  docs: { doc_id: string; hits: number }[];
  results: SearchResult[];
}

interface Props {
  onOpenPdf: (docId: string, page: number) => void;
  onEscalate?: (query: string) => void;
}

/**
 * Pasal.id-style fast retrieval UI. Debounced input, result list grouped
 * by doc with hit counts, search-term highlighting, "Lihat PDF" per row.
 * For complex synthesis the user hands off to Mode Agen via onEscalate.
 */
export function FastSearch({ onOpenPdf, onEscalate }: Props) {
  const [value, setValue] = useState("");
  const [data, setData] = useState<SearchResponse | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [activeIndex, setActiveIndex] = useState(0);
  const acRef = useRef<AbortController | null>(null);
  const debounceRef = useRef<number | null>(null);
  const listRef = useRef<HTMLUListElement | null>(null);

  const doSearch = useCallback(async (q: string) => {
    acRef.current?.abort();
    const trimmed = q.trim();
    if (trimmed.length === 0) {
      setData(null);
      setError(null);
      setLoading(false);
      return;
    }
    const ac = new AbortController();
    acRef.current = ac;
    setLoading(true);
    setError(null);
    try {
      const url =
        `${API_BASE.replace(/\/$/, "")}/api/search` +
        `?q=${encodeURIComponent(trimmed)}&limit=20`;
      const r = await fetch(url, { signal: ac.signal });
      if (!r.ok) throw new Error(`HTTP ${r.status}`);
      const j = (await r.json()) as SearchResponse;
      setData(j);
    } catch (e) {
      if ((e as Error).name === "AbortError") return;
      setError((e as Error).message);
      setData(null);
    } finally {
      if (!ac.signal.aborted) setLoading(false);
    }
  }, []);

  useEffect(() => {
    if (debounceRef.current) window.clearTimeout(debounceRef.current);
    debounceRef.current = window.setTimeout(() => {
      void doSearch(value);
    }, 220);
    return () => {
      if (debounceRef.current) window.clearTimeout(debounceRef.current);
    };
  }, [value, doSearch]);

  // Reset keyboard selection whenever the result list itself changes
  // (new query → fresh results → pointer back to the top).
  useEffect(() => {
    setActiveIndex(0);
  }, [data?.query, data?.count]);

  // Scroll the active row into view on arrow-key navigation so the user
  // doesn't lose track when they move past the viewport.
  useEffect(() => {
    if (!listRef.current) return;
    const node = listRef.current.querySelector<HTMLElement>(
      `[data-index="${activeIndex}"]`,
    );
    node?.scrollIntoView({ block: "nearest", behavior: "smooth" });
  }, [activeIndex]);

  const handleInputKeyDown = (e: React.KeyboardEvent<HTMLInputElement>) => {
    const total = data?.results.length ?? 0;
    if (!total) return;
    if (e.key === "ArrowDown") {
      e.preventDefault();
      setActiveIndex((i) => Math.min(total - 1, i + 1));
    } else if (e.key === "ArrowUp") {
      e.preventDefault();
      setActiveIndex((i) => Math.max(0, i - 1));
    } else if (e.key === "Enter") {
      e.preventDefault();
      const r = data!.results[activeIndex];
      if (r) onOpenPdf(r.doc_id, r.page);
    }
  };

  // Terms for highlighting: drop short tokens, strip punctuation.
  const terms = useMemo(() => {
    return value
      .toLowerCase()
      .split(/\s+/)
      .map((t) => t.replace(/[^\p{L}\p{N}-]/gu, ""))
      .filter((t) => t.length >= 2);
  }, [value]);

  return (
    <div>
      <label htmlFor="fast-q" className="chapter-mark block mb-2">
        Cari Pedoman Indonesia
      </label>
      <div className="flex items-center gap-3 bg-white border border-paper-edge rounded-lg shadow-card focus-within:shadow-card-hover transition-shadow px-4 py-2.5">
        <SearchIcon />
        <input
          id="fast-q"
          type="text"
          value={value}
          onChange={(e) => setValue(e.target.value)}
          onKeyDown={handleInputKeyDown}
          placeholder="contoh: DBD anak · OAT lini pertama · preeklampsia"
          className="flex-1 bg-transparent border-0 focus:outline-none
                     text-body-lg text-ink placeholder:text-ink-ghost"
          aria-activedescendant={
            data && data.results.length > 0 ? `fast-r-${activeIndex}` : undefined
          }
          role="combobox"
          aria-controls="fast-results"
          aria-expanded={Boolean(data && data.results.length > 0)}
        />
        {loading && <Spinner />}
        {value && !loading && (
          <button
            onClick={() => setValue("")}
            className="text-ink-ghost hover:text-ink-mid text-sm font-mono"
            title="Bersihkan"
          >
            ×
          </button>
        )}
      </div>

      {error && (
        <div className="mt-4 text-body text-oxblood">
          Error: {error}
        </div>
      )}

      {data && data.count === 0 && !loading && (
        <div className="mt-10 text-center py-10 border border-dashed border-paper-edge rounded-lg">
          <p className="text-body-lg text-ink-mid">
            Tidak ada kecocokan untuk "{data.query}".
          </p>
          {onEscalate && (
            <button
              onClick={() => onEscalate(data.query)}
              className="mt-3 text-caption font-mono uppercase tracking-editorial text-civic hover:text-civic-hover"
            >
              Coba Mode Agen →
            </button>
          )}
        </div>
      )}

      {data && data.count > 0 && (
        <>
          <div className="mt-5 flex items-center justify-between flex-wrap gap-3">
            <div className="text-caption text-ink-faint font-mono uppercase tracking-editorial">
              <span className="text-ink font-semibold">{data.count}</span> kecocokan
              · <span className="text-ink font-semibold">{data.docs.length}</span> dokumen
            </div>
            {onEscalate && (
              <button
                onClick={() => onEscalate(data.query)}
                className="text-caption font-mono uppercase tracking-editorial
                           text-civic hover:text-civic-hover
                           border-b border-civic/40 hover:border-civic"
              >
                Butuh ringkasan kutip? Mode Agen →
              </button>
            )}
          </div>

          <div className="mt-3 flex flex-wrap gap-2">
            {data.docs.map((d) => (
              <span
                key={d.doc_id}
                className="source-pill !normal-case"
                title={`${d.hits} kecocokan di ${d.doc_id}`}
              >
                <span className="font-mono">{d.doc_id}</span>
                <span className="ml-1.5 opacity-60">·{d.hits}</span>
              </span>
            ))}
          </div>

          <ul
            id="fast-results"
            ref={listRef}
            role="listbox"
            className="mt-5 space-y-2.5"
          >
            {data.results.map((r, i) => (
              <ResultRow
                key={`${r.doc_id}-${r.page}-${r.section_slug}-${i}`}
                result={r}
                terms={terms}
                index={i}
                active={i === activeIndex}
                onFocus={() => setActiveIndex(i)}
                onOpenPdf={() => onOpenPdf(r.doc_id, r.page)}
              />
            ))}
          </ul>
        </>
      )}

      {!data && !loading && !error && (
        <div className="mt-10 text-center py-12 border border-dashed border-paper-edge rounded-lg">
          <p className="text-body-lg text-ink-mid">
            Ketik istilah klinis, nama kondisi, atau bagian PNPK.
          </p>
          <p className="mt-1 text-caption text-ink-faint max-w-[52ch] mx-auto">
            Hasil langsung dari korpus terindeks — tanpa agen, tanpa sintesis,
            tanpa biaya LLM. Buka PDF untuk membaca penuh.
          </p>
          <p className="mt-4 text-caption font-mono uppercase tracking-editorial text-ink-faint inline-flex items-center gap-1.5">
            <KbdHint>↑</KbdHint><KbdHint>↓</KbdHint> pindah hasil
            <span className="text-ink-ghost mx-2">·</span>
            <KbdHint>↵</KbdHint> buka PDF
          </p>
        </div>
      )}
    </div>
  );
}

function ResultRow({
  result,
  terms,
  index,
  active,
  onFocus,
  onOpenPdf,
}: {
  result: SearchResult;
  terms: string[];
  index: number;
  active: boolean;
  onFocus: () => void;
  onOpenPdf: () => void;
}) {
  const sourceType = result.doc_id.startsWith("ppk-fktp")
    ? "PPK FKTP"
    : result.doc_id.startsWith("pnpk")
    ? "PNPK"
    : result.source_type.toUpperCase();
  return (
    <li
      data-index={index}
      id={`fast-r-${index}`}
      role="option"
      aria-selected={active}
    >
      <button
        type="button"
        onClick={onOpenPdf}
        onMouseEnter={onFocus}
        className={`w-full text-left doc-card cursor-pointer transition-colors
                    hover:border-civic/30
                    ${active ? "border-civic/60 bg-civic/5 shadow-card" : ""}`}
      >
        <div className="flex items-center gap-2 flex-wrap mb-1">
          <span className="source-pill">{sourceType}</span>
          <span className="text-caption text-ink-faint font-mono">
            {result.year}
          </span>
          <span className="text-caption text-ink-faint font-mono">·</span>
          <span className="text-caption text-ink-faint font-mono">
            skor {(result.score ?? 0).toFixed(3)}
          </span>
        </div>
        <div className="font-mono text-[0.82rem] text-ink-mid break-all">
          <span className="text-ink font-medium">{result.doc_id}</span>
          <span className="text-ink-ghost"> · </span>
          <span>hal {result.page}</span>
          <span className="text-ink-ghost"> · </span>
          <span>{result.section_slug}</span>
        </div>
        <p className="mt-2 text-body leading-relaxed text-ink-mid">
          {highlight(truncate(result.text, 360), terms)}
        </p>
        <div className="mt-2 text-caption font-mono uppercase tracking-editorial text-civic inline-flex items-center gap-1">
          Lihat PDF, hal {result.page}
          <span aria-hidden="true">→</span>
        </div>
      </button>
    </li>
  );
}

function highlight(text: string, terms: string[]): React.ReactNode {
  if (terms.length === 0) return text;
  // Build a regex that matches any of the terms, case-insensitive, with
  // whole-word-ish boundaries loosened to allow Bahasa-Indonesian
  // suffixation ("DBD" matches in "DBDnya" — acceptable for highlighting).
  const escaped = terms
    .filter((t) => t.length > 0)
    .map((t) => t.replace(/[.*+?^${}()|[\]\\]/g, "\\$&"))
    .join("|");
  if (!escaped) return text;
  const re = new RegExp(`(${escaped})`, "giu");
  const parts = text.split(re);
  return parts.map((p, i) =>
    i % 2 === 1 ? (
      <mark key={i} className="bg-amber/20 text-ink rounded px-0.5">
        {p}
      </mark>
    ) : (
      p
    ),
  );
}

function truncate(s: string, n: number): string {
  const clean = s.replace(/\s+/g, " ").trim();
  return clean.length > n ? clean.slice(0, n - 1) + "…" : clean;
}

function SearchIcon() {
  return (
    <svg
      width="18"
      height="18"
      viewBox="0 0 18 18"
      fill="none"
      stroke="currentColor"
      strokeWidth="1.5"
      strokeLinecap="round"
      className="text-ink-faint shrink-0"
    >
      <circle cx="8" cy="8" r="5.5" />
      <path d="M12 12 L15.5 15.5" />
    </svg>
  );
}

function Spinner() {
  return (
    <span
      aria-label="mencari"
      className="inline-block w-3.5 h-3.5 rounded-full border-2 border-civic/30 border-t-civic animate-spin"
    />
  );
}

function KbdHint({ children }: { children: React.ReactNode }) {
  return (
    <kbd className="inline-flex items-center justify-center min-w-[1.3em] h-[1.3em]
                    px-1 mx-0.5 rounded border border-paper-edge bg-white
                    font-mono text-[0.7rem] text-ink-mid leading-none">
      {children}
    </kbd>
  );
}
