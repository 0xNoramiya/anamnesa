"use client";

import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { useI18n } from "@/components/shell/LanguageProvider";

const API_BASE = process.env.NEXT_PUBLIC_ANAMNESA_API ?? "";

interface LookupResultRow {
  page: number;
  section_slug: string;
  hits: number;
  snippet: string;
}

interface LookupResponse {
  query: string;
  matched_query: string;
  translit_used: boolean;
  doc_id: string;
  doc_title: string;
  source_url: string;
  total_hits: number;
  total_pages: number;
  results: LookupResultRow[];
}

const EXAMPLES = [
  "parasetamol",
  "amoksisilin",
  "metformin",
  "amlodipin",
  "siprofloksasin",
  "kloramfenikol",
];

/**
 * Drug / formulary lookup against Fornas 2023 (Kepmenkes 2197/2023).
 *
 * Pure text search through the page-chunked Fornas PDF — no LLM, no
 * network roundtrip beyond the single GET. Target p95 < 300 ms. Each
 * result links to the corresponding page anchor in the Fornas HTML
 * guideline so doctors can read the surrounding table without
 * downloading the PDF.
 */
export function DrugLookup() {
  const { t } = useI18n();
  const [value, setValue] = useState("");
  const [data, setData] = useState<LookupResponse | null>(null);
  const [loading, setLoading] = useState(false);
  const [elapsed, setElapsed] = useState<number | null>(null);
  const [error, setError] = useState<string | null>(null);
  const acRef = useRef<AbortController | null>(null);
  const debounceRef = useRef<number | null>(null);
  const inputRef = useRef<HTMLInputElement | null>(null);

  const run = useCallback(async (q: string) => {
    acRef.current?.abort();
    const trimmed = q.trim();
    if (trimmed.length < 2) {
      setData(null);
      setError(null);
      setLoading(false);
      setElapsed(null);
      return;
    }
    const ac = new AbortController();
    acRef.current = ac;
    setLoading(true);
    setError(null);
    const start = performance.now();
    try {
      const url =
        `${API_BASE.replace(/\/$/, "")}/api/drug-lookup` +
        `?q=${encodeURIComponent(trimmed)}&limit=20`;
      const r = await fetch(url, { signal: ac.signal });
      if (!r.ok) throw new Error(`HTTP ${r.status}`);
      const j = (await r.json()) as LookupResponse;
      setData(j);
      setElapsed(Math.round(performance.now() - start));
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
      void run(value);
    }, 180);
    return () => {
      if (debounceRef.current) window.clearTimeout(debounceRef.current);
    };
  }, [value, run]);

  // Autofocus the input so power users can start typing immediately.
  useEffect(() => {
    inputRef.current?.focus();
  }, []);

  const matched = data?.matched_query ?? "";

  const guidelineHref = (page: number) =>
    `${API_BASE.replace(/\/$/, "")}/api/guideline/${data?.doc_id ?? "fornas-2023"}.html#halaman-${page}`;

  const pdfHref = (page: number) =>
    `${API_BASE.replace(/\/$/, "")}/api/pdf/${data?.doc_id ?? "fornas-2023"}#page=${page}`;

  return (
    <div style={{ maxWidth: 980, margin: "0 auto", padding: "20px 20px 40px" }}>
      {/* Source strip */}
      <div
        className="mono"
        style={{
          fontSize: 10.5,
          letterSpacing: "0.14em",
          textTransform: "uppercase",
          color: "var(--ink-3)",
          marginBottom: 8,
        }}
      >
        {t("obat.source")}
      </div>

      {/* Input */}
      <div
        style={{
          display: "flex",
          alignItems: "center",
          gap: 12,
          background: "var(--paper)",
          border: "1px solid var(--rule)",
          borderRadius: 2,
          padding: "12px 14px",
        }}
      >
        <SearchIcon />
        <input
          ref={inputRef}
          type="text"
          value={value}
          onChange={(e) => setValue(e.target.value)}
          placeholder={t("obat.placeholder")}
          style={{
            flex: 1,
            background: "transparent",
            border: "none",
            outline: "none",
            fontSize: 17,
            fontFamily: "var(--font-body-stack)",
            color: "var(--ink)",
          }}
          autoComplete="off"
          spellCheck={false}
          aria-label={t("obat.placeholder")}
        />
        {loading && <Spinner />}
        {value && !loading && (
          <button
            onClick={() => setValue("")}
            aria-label={t("obat.clear")}
            className="mono"
            style={{
              background: "transparent",
              border: "none",
              color: "var(--ink-3)",
              cursor: "pointer",
              fontSize: 18,
              padding: "2px 6px",
            }}
          >
            ×
          </button>
        )}
      </div>

      {/* Examples (only when no active query) */}
      {!value && (
        <div style={{ marginTop: 14, display: "flex", flexWrap: "wrap", gap: 8 }}>
          <span
            className="mono"
            style={{
              fontSize: 10.5,
              color: "var(--ink-3)",
              letterSpacing: "0.12em",
              textTransform: "uppercase",
              alignSelf: "center",
              marginRight: 4,
            }}
          >
            {t("obat.examples")}
          </span>
          {EXAMPLES.map((x) => (
            <button
              key={x}
              onClick={() => setValue(x)}
              style={{
                padding: "5px 10px",
                background: "var(--paper)",
                border: "1px solid var(--rule)",
                borderRadius: 2,
                fontSize: 12.5,
                color: "var(--ink-2)",
                cursor: "pointer",
                fontFamily: "var(--font-body-stack)",
              }}
            >
              {x}
            </button>
          ))}
        </div>
      )}

      {/* Error */}
      {error && (
        <div
          style={{
            marginTop: 20,
            padding: 14,
            background: "var(--oxblood-bg, rgba(160, 40, 40, 0.06))",
            border: "1px solid var(--oxblood, #a02828)",
            borderRadius: 2,
            color: "var(--oxblood, #a02828)",
            fontSize: 14,
          }}
        >
          {error}
        </div>
      )}

      {/* Transliteration banner */}
      {data && data.translit_used && (
        <div
          style={{
            marginTop: 18,
            padding: "10px 14px",
            background: "var(--paper-2)",
            border: "1px solid var(--rule)",
            borderLeft: "2px solid var(--teal, #2a7a7a)",
            borderRadius: 2,
            fontSize: 13,
            color: "var(--ink-2)",
            lineHeight: 1.55,
          }}
        >
          {t("obat.translit").replace("{q}", data.query).replace("{t}", data.matched_query)}
        </div>
      )}

      {/* Empty results */}
      {data && data.total_pages === 0 && !loading && (
        <div
          style={{
            marginTop: 30,
            padding: "28px 20px",
            textAlign: "center",
            background: "var(--paper)",
            border: "1px dashed var(--rule)",
            borderRadius: 2,
            color: "var(--ink-3)",
            fontSize: 14,
          }}
        >
          <div style={{ fontSize: 16, color: "var(--ink-2)", marginBottom: 6 }}>
            {t("obat.empty.title").replace("{q}", data.query)}
          </div>
          <div>{t("obat.empty.hint")}</div>
        </div>
      )}

      {/* Results header */}
      {data && data.total_pages > 0 && (
        <>
          <div
            className="mono"
            style={{
              marginTop: 22,
              marginBottom: 10,
              fontSize: 11,
              color: "var(--ink-3)",
              letterSpacing: "0.12em",
              textTransform: "uppercase",
              display: "flex",
              alignItems: "center",
              gap: 10,
              flexWrap: "wrap",
            }}
          >
            <span>
              <strong style={{ color: "var(--ink)" }}>{data.total_pages}</strong>{" "}
              {t("obat.pages_label")}
              {" · "}
              <strong style={{ color: "var(--ink)" }}>{data.total_hits}</strong>{" "}
              {t("obat.hits_label")}
            </span>
            {elapsed != null && (
              <span style={{ color: "var(--ink-4)" }}>· {elapsed} ms</span>
            )}
          </div>

          <ul style={{ listStyle: "none", padding: 0, margin: 0 }}>
            {data.results.map((r) => (
              <li
                key={r.page}
                style={{
                  marginBottom: 12,
                  padding: "14px 16px",
                  background: "var(--paper)",
                  border: "1px solid var(--rule)",
                  borderRadius: 2,
                }}
              >
                <div
                  style={{
                    display: "flex",
                    alignItems: "baseline",
                    justifyContent: "space-between",
                    gap: 12,
                    marginBottom: 8,
                    flexWrap: "wrap",
                  }}
                >
                  <div style={{ display: "flex", alignItems: "baseline", gap: 10 }}>
                    <span
                      className="mono"
                      style={{
                        fontSize: 11,
                        color: "var(--ink-3)",
                        letterSpacing: "0.12em",
                        textTransform: "uppercase",
                      }}
                    >
                      {t("obat.page")}
                    </span>
                    <span
                      className="mono"
                      style={{ fontSize: 16, color: "var(--ink)", fontWeight: 600 }}
                    >
                      {r.page}
                    </span>
                    <span
                      className="mono"
                      style={{ fontSize: 11, color: "var(--ink-4)" }}
                    >
                      {r.hits} {r.hits === 1 ? t("obat.hit_1") : t("obat.hit_n")}
                    </span>
                  </div>
                  <div style={{ display: "flex", gap: 10 }}>
                    <a
                      href={guidelineHref(r.page)}
                      target="_blank"
                      rel="noopener noreferrer"
                      className="mono"
                      style={{
                        fontSize: 11.5,
                        color: "var(--teal, #2a7a7a)",
                        letterSpacing: "0.08em",
                        textTransform: "uppercase",
                        textDecoration: "none",
                        borderBottom: "1px solid var(--teal, #2a7a7a)",
                      }}
                    >
                      {t("obat.open_in_doc")} →
                    </a>
                    <a
                      href={pdfHref(r.page)}
                      target="_blank"
                      rel="noopener noreferrer"
                      className="mono"
                      style={{
                        fontSize: 11.5,
                        color: "var(--ink-3)",
                        letterSpacing: "0.08em",
                        textTransform: "uppercase",
                        textDecoration: "none",
                      }}
                    >
                      PDF
                    </a>
                  </div>
                </div>
                <p
                  style={{
                    margin: 0,
                    fontSize: 13.5,
                    lineHeight: 1.6,
                    color: "var(--ink-2)",
                    whiteSpace: "pre-wrap",
                    fontFamily: "var(--font-body-stack)",
                  }}
                >
                  {highlightTerm(r.snippet, matched)}
                </p>
              </li>
            ))}
          </ul>

          {data.total_pages > data.results.length && (
            <div
              className="mono"
              style={{
                marginTop: 6,
                fontSize: 11,
                color: "var(--ink-4)",
                letterSpacing: "0.1em",
                textTransform: "uppercase",
              }}
            >
              {t("obat.truncated").replace(
                "{n}",
                String(data.total_pages - data.results.length),
              )}
            </div>
          )}
        </>
      )}

      {/* Footnote */}
      <div
        style={{
          marginTop: 28,
          paddingTop: 14,
          borderTop: "1px solid var(--rule)",
          fontSize: 11.5,
          color: "var(--ink-3)",
          lineHeight: 1.6,
        }}
      >
        {t("obat.footnote")}
      </div>
    </div>
  );
}

function SearchIcon() {
  return (
    <svg
      width="18"
      height="18"
      viewBox="0 0 24 24"
      fill="none"
      stroke="var(--ink-3)"
      strokeWidth="1.7"
      strokeLinecap="round"
      strokeLinejoin="round"
      aria-hidden="true"
    >
      <circle cx="11" cy="11" r="6" />
      <path d="M20 20l-4.5-4.5" />
    </svg>
  );
}

function Spinner() {
  return (
    <span
      aria-hidden="true"
      style={{
        display: "inline-block",
        width: 14,
        height: 14,
        border: "2px solid var(--rule)",
        borderTopColor: "var(--navy, #1a2550)",
        borderRadius: "50%",
        animation: "anamnesa-spin 0.7s linear infinite",
      }}
    />
  );
}

/**
 * Wrap every occurrence of `term` (case-insensitive) with a <mark>.
 * Used to visually pin the matched drug name in each snippet.
 */
function highlightTerm(text: string, term: string): React.ReactNode[] {
  if (!term) return [text];
  const lower = text.toLowerCase();
  const t = term.toLowerCase();
  const out: React.ReactNode[] = [];
  let i = 0;
  let k = 0;
  while (i < text.length) {
    const next = lower.indexOf(t, i);
    if (next < 0) {
      out.push(text.slice(i));
      break;
    }
    if (next > i) out.push(text.slice(i, next));
    out.push(
      <mark
        key={`m-${k++}`}
        style={{
          background: "var(--teal-tint, rgba(42, 122, 122, 0.18))",
          color: "var(--ink)",
          padding: "0 2px",
          borderRadius: 2,
        }}
      >
        {text.slice(next, next + t.length)}
      </mark>,
    );
    i = next + t.length;
  }
  return out;
}
