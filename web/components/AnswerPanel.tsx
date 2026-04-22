"use client";

import type { Citation, CurrencyFlag, FinalResponse } from "@/lib/types";
import { REFUSAL_MESSAGES_ID } from "@/lib/refusalMessages";

interface Props {
  final: FinalResponse | null;
}

/**
 * Journal-article-style answer panel. Renders the Drafter's content,
 * swaps inline [[key]] markers for superscript citation numbers, and
 * lays out a numbered reference list with a currency badge per entry.
 * Refusal cases render a distinct oxblood editorial note.
 */
export function AnswerPanel({ final }: Props) {
  if (!final) return null;

  if (final.refusal_reason) {
    return <Refusal final={final} />;
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
      <div className="flex items-center gap-3 mb-2">
        <span className="chapter-mark">Jawaban Anamnesa</span>
        <span className="flex-1 rule" />
        <span className="chapter-mark">
          {citations.length} kutipan · {final.currency_flags.length} bendera
        </span>
      </div>

      <BodyProse
        content={final.answer_markdown}
        indexByKey={indexByKey}
      />

      <section className="mt-12">
        <div className="flex items-center gap-3 mb-3">
          <span className="chapter-mark">Referensi</span>
          <span className="flex-1 rule" />
        </div>
        <ol className="space-y-4">
          {citations.map((c, i) => (
            <ReferenceItem
              key={c.key}
              index={i + 1}
              citation={c}
              flag={flagsByKey.get(c.key)}
            />
          ))}
        </ol>
      </section>

      <Disclaimer />
    </article>
  );
}

function BodyProse({
  content,
  indexByKey,
}: {
  content: string;
  indexByKey: Map<string, number>;
}) {
  // Parse: replace inline [[key]] with superscripts linked to the
  // reference list. We keep paragraph breaks but strip markdown heading
  // hashes — we style them ourselves.
  const paragraphs = content
    .split(/\n{2,}/)
    .map((p) => p.trim())
    .filter(Boolean);

  return (
    <div className="prose-anamnesa">
      {paragraphs.map((p, i) => {
        const isHeading = /^#{2,6}\s+/.test(p);
        if (isHeading) {
          const text = p.replace(/^#{2,6}\s+/, "");
          return (
            <h3
              key={i}
              className="font-display text-display-md text-ink mt-8 mb-3"
            >
              {text}
            </h3>
          );
        }
        const isList = /^[-*]\s+/.test(p);
        if (isList) {
          const items = p.split(/\n/).map((l) => l.replace(/^[-*]\s+/, ""));
          return (
            <ul key={i} className="my-4 ml-6 list-disc marker:text-oxblood space-y-2">
              {items.map((item, j) => (
                <li key={j} className="text-body-lg leading-relaxed text-ink">
                  {renderInline(item, indexByKey)}
                </li>
              ))}
            </ul>
          );
        }
        const firstParagraphClasses = i === 0 ? "drop-cap" : "";
        return (
          <p
            key={i}
            className={`text-body-lg leading-relaxed text-ink my-4 ${firstParagraphClasses}`}
          >
            {renderInline(p, indexByKey)}
          </p>
        );
      })}
    </div>
  );
}

/** Replace [[doc_id:pN:section]] with superscript links. */
function renderInline(
  text: string,
  indexByKey: Map<string, number>,
): React.ReactNode[] {
  const parts: React.ReactNode[] = [];
  const re = /\[\[([^\]]+)\]\]/g;
  let last = 0;
  let match: RegExpExecArray | null;
  let counter = 0;
  while ((match = re.exec(text)) !== null) {
    if (match.index > last) parts.push(text.slice(last, match.index));
    const key = match[1];
    const n = indexByKey.get(key);
    parts.push(
      <a
        key={`c-${counter++}`}
        href={`#ref-${key}`}
        className="cite-marker"
        title={key}
      >
        {n ?? "?"}
      </a>,
    );
    last = match.index + match[0].length;
  }
  if (last < text.length) parts.push(text.slice(last));
  return parts;
}

function ReferenceItem({
  index,
  citation,
  flag,
}: {
  index: number;
  citation: Citation;
  flag?: CurrencyFlag;
}) {
  return (
    <li id={`ref-${citation.key}`} className="flex gap-4">
      <div className="font-mono text-sm text-oxblood shrink-0 pt-0.5 w-6 text-right tabular-nums">
        {index}.
      </div>
      <div className="flex-1 min-w-0">
        <div className="flex items-baseline gap-3 flex-wrap">
          <span className="font-mono text-[0.78rem] text-ink-mid break-all">
            {citation.doc_id}
            <span className="text-ink-ghost"> · p</span>
            <span className="tabular-nums">{citation.page}</span>
            <span className="text-ink-ghost"> · </span>
            <span>{citation.section_slug}</span>
          </span>
          {flag && <CurrencyStamp flag={flag} />}
        </div>
        <blockquote className="mt-2 pl-3 border-l-2 border-paper-edge italic text-ink-mid text-body leading-relaxed">
          {truncate(citation.chunk_text, 360)}
        </blockquote>
        <a
          href={`/api/pdf/${citation.doc_id}#page=${citation.page}`}
          target="_blank"
          rel="noreferrer"
          className="inline-block mt-2 text-caption font-mono uppercase tracking-editorial text-indigo hover:text-ink transition-colors"
        >
          Buka PDF · hal {citation.page} →
        </a>
      </div>
    </li>
  );
}

function CurrencyStamp({ flag }: { flag: CurrencyFlag }) {
  const label = STATUS_LABELS_ID[flag.status];
  const stampClass = `stamp stamp-${flag.status}`;
  return (
    <span className={stampClass} title={`Terbit ${flag.source_year}`}>
      <span>{label}</span>
      <span className="opacity-60">· {flag.source_year}</span>
    </span>
  );
}

const STATUS_LABELS_ID: Record<string, string> = {
  current:    "Berlaku",
  aging:      "Menua",
  superseded: "Digantikan",
  withdrawn:  "Dicabut",
  unknown:    "Tak Diketahui",
};

function truncate(s: string, n: number): string {
  const clean = s.replace(/\s+/g, " ").trim();
  return clean.length > n ? clean.slice(0, n - 1) + "…" : clean;
}

function Refusal({ final }: { final: FinalResponse }) {
  const reason = final.refusal_reason!;
  const msg = REFUSAL_MESSAGES_ID[reason] ?? final.answer_markdown;
  return (
    <article className="animate-fade-in-up">
      <div className="flex items-center gap-3 mb-3">
        <span className="chapter-mark text-oxblood">Penolakan · Refusal</span>
        <span className="flex-1 rule" />
        <span className="chapter-mark">{reason}</span>
      </div>
      <div className="border-l-4 border-oxblood pl-6 py-4">
        <p className="text-body-lg leading-relaxed text-ink">{msg}</p>
        <p className="mt-4 text-caption text-ink-faint font-mono uppercase tracking-editorial">
          Anamnesa menolak menghasilkan jawaban tanpa dasar pedoman.
        </p>
      </div>
      <Disclaimer />
    </article>
  );
}

function Disclaimer() {
  return (
    <footer className="mt-12 pt-6 border-t border-paper-edge">
      <p className="text-caption text-ink-faint leading-relaxed max-w-[56ch]">
        <strong className="text-ink-mid">Anamnesa</strong> membantu dokter
        menemukan dan mengutip pedoman Indonesia yang berlaku. Ini bukan
        alat diagnosis atau rekomendasi terapi untuk pasien individual.
        Keputusan klinis tetap menjadi tanggung jawab dokter.
      </p>
    </footer>
  );
}
