"use client";

import { useState } from "react";
import type {
  Citation,
  CurrencyFlag,
  FinalResponse,
  RetrievalHint,
} from "@/lib/types";
import { REFUSAL_MESSAGES_ID } from "@/lib/refusalMessages";
import {
  buildAnswerMarkdown,
  downloadText,
  suggestedFilename,
} from "@/lib/exportMarkdown";
import { FeedbackBar } from "./FeedbackBar";

interface Props {
  final: FinalResponse | null;
  queryText?: string;
  onOpenPdf?: (docId: string, page: number) => void;
}

export function AnswerPanel({ final, queryText, onOpenPdf }: Props) {
  // Track which citation the user is hovering so we can bidirectionally
  // halo inline markers and the matching reference card. Lifted here
  // because BodyProse and the card list are siblings in this component.
  const [hoveredKey, setHoveredKey] = useState<string | null>(null);

  if (!final) return null;
  if (final.refusal_reason) {
    return <Refusal final={final} queryText={queryText} onOpenPdf={onOpenPdf} />;
  }

  const citations = final.citations;
  const flagsByKey = new Map<string, CurrencyFlag>(
    final.currency_flags.map((f) => [f.citation_key, f]),
  );
  const indexByKey = new Map<string, number>(
    citations.map((c, i) => [c.key, i + 1]),
  );

  return (
    <article className="animate-fade-in-up">
      <div className="flex items-center gap-3 mb-3">
        <span className="chapter-mark">Jawaban</span>
        <span className="flex-1 h-px bg-paper-edge" />
        <span className="chapter-mark text-ink-faint">
          {citations.length} kutipan
          {final.currency_flags.length > 0 && (
            <> · {final.currency_flags.length} bendera</>
          )}
        </span>
      </div>

      {final.from_cache && <CacheBadge ageSeconds={final.cached_age_s ?? null} />}

      <ExportActions final={final} queryText={queryText} />

      <BodyProse
        content={final.answer_markdown}
        indexByKey={indexByKey}
        hoveredKey={hoveredKey}
        onHover={setHoveredKey}
      />

      <section className="mt-10">
        <div className="flex items-center gap-3 mb-4">
          <h2 className="chapter-mark">Referensi</h2>
          <span className="flex-1 h-px bg-paper-edge" />
        </div>
        <div className="space-y-3">
          {citations.map((c, i) => (
            <ReferenceCard
              key={c.key}
              index={i + 1}
              citation={c}
              flag={flagsByKey.get(c.key)}
              highlighted={hoveredKey === c.key}
              onHoverChange={(on) => setHoveredKey(on ? c.key : null)}
              onOpenPdf={onOpenPdf}
            />
          ))}
        </div>
      </section>

      <FeedbackBar final={final} queryText={queryText} />

      <Disclaimer />
    </article>
  );
}

function BodyProse({
  content,
  indexByKey,
  hoveredKey,
  onHover,
}: {
  content: string;
  indexByKey: Map<string, number>;
  hoveredKey: string | null;
  onHover: (key: string | null) => void;
}) {
  const paragraphs = content
    .split(/\n{2,}/)
    .map((p) => p.trim())
    .filter(Boolean);

  const render = (text: string) =>
    renderInline(text, indexByKey, hoveredKey, onHover);

  return (
    <div className="text-ink">
      {paragraphs.map((p, i) => {
        const headingMatch = /^(#{2,6})\s+(.*)$/s.exec(p);
        if (headingMatch) {
          const text = headingMatch[2];
          return (
            <h3
              key={i}
              className="font-semibold text-ink text-lg mt-8 mb-3"
            >
              {render(text)}
            </h3>
          );
        }

        // Pipe-delimited markdown tables (GFM-ish). Detect: every
        // non-blank line starts and ends with "|", and the 2nd line is
        // a separator ("| --- | --- |").
        const tableNodes = maybeRenderTable(p, indexByKey, i, hoveredKey, onHover);
        if (tableNodes) return tableNodes;

        if (/^[-*]\s+/m.test(p)) {
          const items = p
            .split(/\n/)
            .filter((l) => /^[-*]\s+/.test(l))
            .map((l) => l.replace(/^[-*]\s+/, ""));
          return (
            <ul key={i} className="my-4 ml-5 list-disc marker:text-civic space-y-1.5">
              {items.map((item, j) => (
                <li key={j} className="text-body-lg leading-relaxed">
                  {render(item)}
                </li>
              ))}
            </ul>
          );
        }
        return (
          <p key={i} className="text-body-lg leading-relaxed my-4">
            {render(p)}
          </p>
        );
      })}
    </div>
  );
}

function maybeRenderTable(
  block: string,
  indexByKey: Map<string, number>,
  key: number,
  hoveredKey: string | null,
  onHover: (key: string | null) => void,
): React.ReactNode | null {
  // Accept both single-line (whole table on one line separated by newlines
  // that got collapsed) and proper multi-line markdown tables.
  // First, try splitting by newlines; if we only get one line containing
  // multiple `| ... |` groups, split those out.
  let lines = block.split(/\n/).map((l) => l.trim()).filter(Boolean);

  if (lines.length === 1 && /\|\s*---/.test(lines[0])) {
    // Single-line table (common when the Drafter emits compact text).
    // Split on the pipe-run boundary: any occurrence of ` | ` after a
    // trailing `|`. Heuristic: split on `| |` which only appears between
    // rows in our cell format.
    lines = lines[0].split(/(?<=\|)\s+(?=\|)/).map((l) => l.trim()).filter(Boolean);
  }

  // Must have at least header + separator + one data row.
  if (lines.length < 3) return null;
  if (!lines.every((l) => l.startsWith("|") && l.endsWith("|"))) return null;
  if (!/^\|\s*[-:]{2,}/.test(lines[1].replace(/\s*\|\s*/g, "|").replace(/^\|/, "|"))) {
    // Separator row check — loose: it must contain at least one cell of
    // 3+ dashes (possibly with leading/trailing colons for alignment).
    if (!lines[1].includes("---")) return null;
  }

  const parseRow = (l: string): string[] =>
    l.slice(1, -1).split("|").map((c) => c.trim());

  const header = parseRow(lines[0]);
  const body = lines.slice(2).map(parseRow);

  return (
    <div key={key} className="my-5 overflow-x-auto -mx-1 px-1">
      <table className="w-full border-collapse text-body">
        <thead>
          <tr className="border-b-2 border-ink">
            {header.map((h, hi) => (
              <th
                key={hi}
                className="text-left font-semibold text-ink py-2 px-3 align-bottom"
              >
                {renderInline(h, indexByKey, hoveredKey, onHover)}
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {body.map((row, ri) => (
            <tr
              key={ri}
              className="border-b border-paper-edge last:border-0"
            >
              {row.map((cell, ci) => (
                <td key={ci} className="py-2 px-3 align-top text-ink-mid">
                  {renderInline(cell, indexByKey, hoveredKey, onHover)}
                </td>
              ))}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

/**
 * Tokenize a paragraph into text + inline markdown + citation markers.
 * Handles `[[doc_id:pN:section]]`, `**bold**`, and `*italic*` in one pass.
 */
function jumpToReference(key: string, event?: React.MouseEvent) {
  if (typeof document === "undefined") return;
  // Let users cmd/ctrl-click to open in a new tab (native anchor behavior).
  if (event && (event.metaKey || event.ctrlKey || event.shiftKey)) return;
  event?.preventDefault();
  const target = document.getElementById(`ref-${key}`);
  if (!target) return;
  target.scrollIntoView({ behavior: "smooth", block: "center" });
  target.classList.add("ref-flash");
  // Remove the class after the animation completes so a re-click retriggers.
  window.setTimeout(() => target.classList.remove("ref-flash"), 1600);
}

function renderInline(
  text: string,
  indexByKey: Map<string, number>,
  hoveredKey: string | null,
  onHover: (key: string | null) => void,
): React.ReactNode[] {
  const parts: React.ReactNode[] = [];
  const re = /\[\[([^\]]+)\]\]|\*\*([^*]+?)\*\*|(?<!\*)\*([^*\n]+?)\*(?!\*)/g;
  let last = 0;
  let match: RegExpExecArray | null;
  let counter = 0;
  while ((match = re.exec(text)) !== null) {
    if (match.index > last) parts.push(text.slice(last, match.index));
    if (match[1] !== undefined) {
      const key = match[1];
      const n = indexByKey.get(key);
      const known = n !== undefined;
      const active = hoveredKey === key;
      parts.push(
        <a
          key={`c-${counter++}`}
          href={`#ref-${key}`}
          onClick={known ? (e) => jumpToReference(key, e) : undefined}
          onMouseEnter={known ? () => onHover(key) : undefined}
          onMouseLeave={known ? () => onHover(null) : undefined}
          className={`cite-marker${active ? " cite-marker-active" : ""}`}
          data-cite-key={key}
          title={known ? `Referensi ${n}: ${key}` : key}
          aria-label={known ? `Lompat ke referensi ${n}` : `Referensi ${key}`}
        >
          {n ?? "?"}
        </a>,
      );
    } else if (match[2] !== undefined) {
      parts.push(
        <strong key={`b-${counter++}`} className="font-semibold text-ink">
          {match[2]}
        </strong>,
      );
    } else if (match[3] !== undefined) {
      parts.push(
        <em key={`i-${counter++}`} className="italic">
          {match[3]}
        </em>,
      );
    }
    last = match.index + match[0].length;
  }
  if (last < text.length) parts.push(text.slice(last));
  return parts;
}

function ReferenceCard({
  index,
  citation,
  flag,
  highlighted,
  onHoverChange,
  onOpenPdf,
}: {
  index: number;
  citation: Citation;
  flag?: CurrencyFlag;
  highlighted?: boolean;
  onHoverChange?: (on: boolean) => void;
  onOpenPdf?: (docId: string, page: number) => void;
}) {
  const [copied, setCopied] = useState(false);
  const sourceType = citation.doc_id.startsWith("ppk-fktp")
    ? "PPK FKTP"
    : citation.doc_id.startsWith("pnpk")
    ? "PNPK"
    : "DOC";

  const handleCopy = async () => {
    const md = formatCitationMarkdown(citation, flag, sourceType);
    try {
      await navigator.clipboard.writeText(md);
    } catch {
      const ta = document.createElement("textarea");
      ta.value = md;
      ta.style.position = "fixed";
      ta.style.opacity = "0";
      document.body.appendChild(ta);
      ta.select();
      try { document.execCommand("copy"); } finally { ta.remove(); }
    }
    setCopied(true);
    setTimeout(() => setCopied(false), 1800);
  };

  return (
    <article
      id={`ref-${citation.key}`}
      data-cite-key={citation.key}
      className={`doc-card transition-all${highlighted ? " ref-highlight" : ""}`}
      onMouseEnter={() => onHoverChange?.(true)}
      onMouseLeave={() => onHoverChange?.(false)}
    >
      <div className="flex items-start gap-3 mb-2">
        <div className="flex-shrink-0 font-mono text-sm text-civic font-semibold tabular-nums pt-0.5 w-6 text-right">
          {index}.
        </div>
        <div className="flex-1 min-w-0">
          <div className="flex items-center gap-2 flex-wrap mb-1">
            <span className="source-pill">{sourceType}</span>
            {flag && <CurrencyBadge flag={flag} />}
          </div>
          <div className="font-mono text-[0.82rem] text-ink-mid break-all">
            <span className="text-ink font-medium">{citation.doc_id}</span>
            <span className="text-ink-ghost"> · </span>
            <span>hal {citation.page}</span>
            <span className="text-ink-ghost"> · </span>
            <span>{citation.section_slug}</span>
          </div>
          <blockquote className="mt-2.5 pl-3 border-l-2 border-paper-edge text-ink-mid text-body leading-relaxed">
            {truncate(citation.chunk_text, 340)}
          </blockquote>
          <div className="mt-3 flex items-center gap-2 flex-wrap">
            <button
              type="button"
              onClick={() => onOpenPdf?.(citation.doc_id, citation.page)}
              className="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-md
                         bg-civic/5 border border-civic/20 text-civic
                         text-caption font-medium
                         hover:bg-civic hover:text-white hover:border-civic
                         transition-colors"
            >
              <svg width="12" height="12" viewBox="0 0 12 12" fill="none" stroke="currentColor" strokeWidth="1.5">
                <rect x="1.5" y="1.5" width="9" height="9" rx="1" />
                <path d="M3.5 4.5h5M3.5 6.5h5M3.5 8.5h3" />
              </svg>
              Lihat PDF, hal {citation.page}
            </button>
            <button
              type="button"
              onClick={handleCopy}
              className="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-md
                         border border-paper-edge text-ink-mid
                         text-caption font-medium
                         hover:border-civic/30 hover:text-civic
                         transition-colors"
              title="Salin kutipan + sumber ke clipboard"
            >
              <svg width="12" height="12" viewBox="0 0 24 24" fill="none"
                   stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                <rect width="14" height="14" x="8" y="8" rx="2" />
                <path d="M4 16V4a2 2 0 0 1 2-2h10" />
              </svg>
              {copied ? "Tersalin ✓" : "Salin kutipan"}
            </button>
          </div>
        </div>
      </div>
    </article>
  );
}

function formatCitationMarkdown(
  citation: Citation,
  flag: CurrencyFlag | undefined,
  sourceType: string,
): string {
  const currency = flag
    ? ` · ${
        flag.status === "aging"
          ? "⚠ Aging"
          : flag.status === "superseded"
            ? `⚠ Superseded → ${flag.superseding_doc_id ?? "?"}`
            : flag.status === "withdrawn"
              ? "⚠ Withdrawn"
              : flag.status === "current"
                ? "✓ Current"
                : flag.status
      } · ${flag.source_year}`
    : "";
  const body = (citation.chunk_text ?? "").replace(/\s+/g, " ").trim();
  return [
    `**${citation.doc_id}** · hal ${citation.page} · ${sourceType}${currency}`,
    `> ${body}`,
  ].join("\n");
}

function CurrencyBadge({ flag }: { flag: CurrencyFlag }) {
  const label = STATUS_LABELS_ID[flag.status];
  return (
    <span className={`badge badge-${flag.status}`} title={`Terbit ${flag.source_year}`}>
      <span>{label}</span>
      <span className="opacity-70">· {flag.source_year}</span>
    </span>
  );
}

const STATUS_LABELS_ID: Record<string, string> = {
  current: "Berlaku",
  aging: "Menua",
  superseded: "Digantikan",
  withdrawn: "Dicabut",
  unknown: "Tak Diketahui",
};

function truncate(s: string, n: number): string {
  const clean = s.replace(/\s+/g, " ").trim();
  return clean.length > n ? clean.slice(0, n - 1) + "…" : clean;
}

function Refusal({
  final,
  queryText,
  onOpenPdf,
}: {
  final: FinalResponse;
  queryText?: string;
  onOpenPdf?: (docId: string, page: number) => void;
}) {
  const reason = final.refusal_reason!;
  const msg = REFUSAL_MESSAGES_ID[reason] ?? final.answer_markdown;
  const hints = final.retrieval_preview ?? [];
  return (
    <article className="animate-fade-in-up">
      <div className="flex items-center gap-3 mb-3">
        <span className="chapter-mark text-oxblood">Penolakan</span>
        <span className="flex-1 h-px bg-oxblood/30" />
        <span className="chapter-mark text-oxblood">{reason}</span>
      </div>
      {final.from_cache && <CacheBadge ageSeconds={final.cached_age_s ?? null} />}

      <ExportActions final={final} queryText={queryText} />

      <div className="bg-oxblood/5 border border-oxblood/20 rounded-lg p-5">
        <p className="text-body-lg leading-relaxed text-ink">{msg}</p>
        <p className="mt-3 text-caption text-oxblood font-mono uppercase tracking-editorial">
          Anamnesa menolak menghasilkan jawaban tanpa dasar pedoman.
        </p>
      </div>

      {hints.length > 0 && (
        <section className="mt-8">
          <div className="flex items-center gap-3 mb-3">
            <span className="chapter-mark text-ink-mid">Hasil Pencarian</span>
            <span className="flex-1 h-px bg-paper-edge" />
            <span className="chapter-mark text-ink-faint">
              {hints.length} dokumen
            </span>
          </div>
          <p className="text-body text-ink-mid leading-relaxed mb-4 max-w-[62ch]">
            Mesin pencari menemukan dokumen berikut, namun Drafter menilai
            isinya tidak cukup untuk menjawab pertanyaan secara aman. Anda
            dapat membuka PDF-nya untuk menilai sendiri.
          </p>
          <div className="space-y-2.5">
            {hints.map((h, i) => (
              <HintCard key={`${h.doc_id}-${h.page}-${i}`} hint={h} onOpenPdf={onOpenPdf} />
            ))}
          </div>
        </section>
      )}

      <Disclaimer />
    </article>
  );
}

function HintCard({
  hint,
  onOpenPdf,
}: {
  hint: RetrievalHint;
  onOpenPdf?: (docId: string, page: number) => void;
}) {
  const sourceType = hint.source_type
    .replace(/_/g, " ")
    .replace(/\b\w/g, (c) => c.toUpperCase());
  return (
    <button
      type="button"
      onClick={() => onOpenPdf?.(hint.doc_id, hint.page)}
      disabled={!onOpenPdf}
      className="w-full text-left bg-white border border-paper-edge rounded-lg
                 p-4 hover:border-civic/40 hover:shadow-card disabled:cursor-default
                 disabled:hover:border-paper-edge disabled:hover:shadow-none
                 transition-all group"
    >
      <div className="flex items-center gap-2 flex-wrap">
        <span className="source-pill shrink-0">{sourceType}</span>
        <span className="font-mono text-caption text-ink-mid truncate">
          {hint.doc_id}
        </span>
        <span className="text-ink-ghost text-caption">·</span>
        <span className="text-caption text-ink-faint">hal {hint.page}</span>
        <span className="text-ink-ghost text-caption">·</span>
        <span className="text-caption text-ink-faint">{hint.year}</span>
        {onOpenPdf && (
          <span className="ml-auto text-caption text-civic opacity-0 group-hover:opacity-100 transition-opacity">
            Buka PDF →
          </span>
        )}
      </div>
      <p className="mt-2 text-body text-ink-mid leading-relaxed line-clamp-3">
        {hint.text_preview}
      </p>
    </button>
  );
}

function Disclaimer() {
  return (
    <footer className="mt-10 pt-5 border-t border-paper-edge">
      <p className="text-caption text-ink-faint leading-relaxed max-w-[62ch]">
        <strong className="text-ink-mid">Anamnesa</strong> membantu dokter
        menemukan dan mengutip pedoman Indonesia yang berlaku. Ini bukan
        alat diagnosis atau rekomendasi terapi untuk pasien individual.
        Keputusan klinis tetap menjadi tanggung jawab dokter.
      </p>
    </footer>
  );
}

function ExportActions({
  final,
  queryText,
}: {
  final: FinalResponse;
  queryText?: string;
}) {
  const [copied, setCopied] = useState(false);

  const buildMd = () => buildAnswerMarkdown(queryText ?? "", final);

  const handleCopy = async () => {
    const md = buildMd();
    try {
      await navigator.clipboard.writeText(md);
      setCopied(true);
      setTimeout(() => setCopied(false), 1800);
    } catch {
      // Clipboard API failed (iframe without permission, http page, etc.)
      // — fall back to selecting + execCommand.
      const ta = document.createElement("textarea");
      ta.value = md;
      ta.style.position = "fixed";
      ta.style.opacity = "0";
      document.body.appendChild(ta);
      ta.select();
      try {
        document.execCommand("copy");
        setCopied(true);
        setTimeout(() => setCopied(false), 1800);
      } finally {
        ta.remove();
      }
    }
  };

  const handleDownload = () => {
    downloadText(suggestedFilename(), buildMd());
  };

  return (
    <div className="mb-5 flex items-center gap-2">
      <button
        type="button"
        onClick={handleCopy}
        className="inline-flex items-center gap-1.5 text-caption font-mono
                   uppercase tracking-editorial text-ink-mid hover:text-civic
                   hover:bg-paper-deep px-2.5 py-1.5 rounded-md transition-colors"
        title="Salin jawaban (Markdown) ke clipboard"
      >
        <svg width="13" height="13" viewBox="0 0 24 24" fill="none"
             stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
          <rect width="14" height="14" x="8" y="8" rx="2" />
          <path d="M4 16V4a2 2 0 0 1 2-2h10" />
        </svg>
        {copied ? "Tersalin ✓" : "Salin"}
      </button>
      <button
        type="button"
        onClick={handleDownload}
        className="inline-flex items-center gap-1.5 text-caption font-mono
                   uppercase tracking-editorial text-ink-mid hover:text-civic
                   hover:bg-paper-deep px-2.5 py-1.5 rounded-md transition-colors"
        title="Unduh sebagai berkas .md"
      >
        <svg width="13" height="13" viewBox="0 0 24 24" fill="none"
             stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
          <path d="M12 3v12" />
          <polyline points="7 10 12 15 17 10" />
          <path d="M5 21h14" />
        </svg>
        Unduh .md
      </button>
    </div>
  );
}

function CacheBadge({ ageSeconds }: { ageSeconds: number | null }) {
  const label = formatCacheAge(ageSeconds);
  return (
    <div
      className="mb-5 flex items-center gap-2 text-caption font-mono uppercase
                 tracking-editorial text-civic bg-civic/5 border border-civic/20
                 rounded-md px-3 py-2"
      title="Jawaban ini diambil dari cache — kueri serupa sudah pernah dijalankan."
    >
      <svg
        width="14"
        height="14"
        viewBox="0 0 24 24"
        fill="none"
        stroke="currentColor"
        strokeWidth="2"
        strokeLinecap="round"
        strokeLinejoin="round"
      >
        <polyline points="20 6 9 17 4 12" />
      </svg>
      <span>Dari cache · {label}</span>
    </div>
  );
}

function formatCacheAge(seconds: number | null): string {
  if (seconds == null) return "baru saja";
  if (seconds < 60) return "baru saja";
  if (seconds < 3600) return `${Math.round(seconds / 60)} menit lalu`;
  if (seconds < 86400) return `${Math.round(seconds / 3600)} jam lalu`;
  return `${Math.round(seconds / 86400)} hari lalu`;
}
