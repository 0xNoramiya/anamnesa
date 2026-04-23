"use client";

import { useMemo } from "react";
import type { TraceEvent } from "@/lib/types";
import { useI18n } from "@/components/shell/LanguageProvider";

interface ChunkPreview {
  doc_id: string;
  page: number;
  section_slug: string;
  year: number;
  source_type: string;
  score: number;
  excerpt: string;
}

interface DocSummary {
  doc_id: string;
  hits: number;
}

interface Props {
  events: TraceEvent[];
  onOpenPdf?: (docId: string, page: number) => void;
}

/**
 * Shows the top retrieved chunks the moment the retriever finishes —
 * typically ~5s into a query — so the user has something concrete to
 * read while the Drafter + Verifier take another 90-120s. Picks up
 * the latest `retriever.searched` event's `previews` payload.
 */
export function RetrievalPreview({ events, onOpenPdf }: Props) {
  const { t } = useI18n();

  const { previews, docs, totalHits } = useMemo(() => {
    // Walk backward for the most recent retrieval (later retrieval
    // attempts refine earlier ones).
    for (let i = events.length - 1; i >= 0; i--) {
      const ev = events[i];
      if (ev.agent === "retriever" && ev.event_type === "searched") {
        const payload = ev.payload as Record<string, unknown>;
        const raw = (payload.previews ?? []) as ChunkPreview[];
        const docList = (payload.docs ?? []) as DocSummary[];
        const total = typeof payload.chunks === "number" ? payload.chunks : raw.length;
        if (raw.length > 0) {
          return { previews: raw, docs: docList, totalHits: total };
        }
      }
    }
    return { previews: [] as ChunkPreview[], docs: [] as DocSummary[], totalHits: 0 };
  }, [events]);

  if (previews.length === 0) return null;

  return (
    <section
      className="animate-fade-in-up"
      style={{
        marginTop: 20,
        border: "1px solid var(--rule)",
        background: "var(--paper-2)",
        borderRadius: 2,
      }}
    >
      <header
        style={{
          display: "flex",
          alignItems: "baseline",
          gap: 12,
          padding: "12px 16px",
          borderBottom: "1px solid var(--rule)",
          flexWrap: "wrap",
        }}
      >
        <span
          className="mono"
          style={{
            fontSize: 10.5,
            color: "var(--teal)",
            letterSpacing: "0.14em",
          }}
        >
          ¶ {t("preview.title").toUpperCase()}
        </span>
        <span style={{ flex: 1, height: 1, background: "var(--rule)", alignSelf: "center" }} />
        <span className="mono" style={{ fontSize: 10.5, color: "var(--ink-3)" }}>
          {totalHits} {t("preview.hits")} · {docs.length} {t("preview.docs")}
        </span>
      </header>

      <div style={{ padding: "10px 16px 14px" }}>
        <p
          style={{
            fontSize: 13,
            color: "var(--ink-2)",
            lineHeight: 1.55,
            margin: "0 0 12px",
            maxWidth: "60ch",
          }}
        >
          {t("preview.sub")}
        </p>

        <ol style={{ listStyle: "none", padding: 0, margin: 0, display: "flex", flexDirection: "column", gap: 10 }}>
          {previews.map((p, i) => (
            <PreviewCard
              key={`${p.doc_id}-${p.page}-${p.section_slug}-${i}`}
              preview={p}
              onOpenPdf={onOpenPdf}
              openLabel={t("preview.open_pdf")}
            />
          ))}
        </ol>
      </div>
    </section>
  );
}

function PreviewCard({
  preview,
  onOpenPdf,
  openLabel,
}: {
  preview: ChunkPreview;
  onOpenPdf?: (docId: string, page: number) => void;
  openLabel: string;
}) {
  const sourceLabel = formatSource(preview.source_type);
  return (
    <li
      style={{
        background: "var(--paper)",
        border: "1px solid var(--rule)",
        borderRadius: 2,
        padding: "10px 12px",
      }}
    >
      <div style={{ display: "flex", alignItems: "center", gap: 8, flexWrap: "wrap" }}>
        <span
          className="mono"
          style={{
            fontSize: 10,
            padding: "1px 6px",
            background: "var(--navy)",
            color: "var(--paper)",
            letterSpacing: "0.06em",
            fontWeight: 500,
          }}
        >
          {sourceLabel}
        </span>
        <span
          className="mono"
          style={{
            fontSize: 11,
            color: "var(--ink-2)",
            overflow: "hidden",
            textOverflow: "ellipsis",
            whiteSpace: "nowrap",
            minWidth: 0,
            flex: 1,
          }}
        >
          {preview.doc_id}
        </span>
        <span className="mono" style={{ fontSize: 10.5, color: "var(--ink-3)" }}>
          hal. {preview.page}
        </span>
        {onOpenPdf && (
          <button
            type="button"
            onClick={() => onOpenPdf(preview.doc_id, preview.page)}
            className="mono"
            style={{
              fontSize: 10.5,
              padding: "2px 8px",
              border: "1px solid var(--rule)",
              background: "transparent",
              color: "var(--navy)",
              cursor: "pointer",
              letterSpacing: "0.04em",
            }}
          >
            {openLabel} ↗
          </button>
        )}
      </div>
      <p
        style={{
          fontSize: 12.5,
          color: "var(--ink-2)",
          lineHeight: 1.55,
          margin: "8px 0 0",
          paddingLeft: 10,
          borderLeft: "2px solid var(--rule-2)",
          fontStyle: "italic",
        }}
      >
        {preview.excerpt}
      </p>
    </li>
  );
}

function formatSource(s: string): string {
  if (s === "ppk_fktp") return "PPK FKTP";
  if (s === "pnpk") return "PNPK";
  if (s === "kemkes_program") return "KEMENKES";
  return s.replace(/_/g, " ").toUpperCase();
}
