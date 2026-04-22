"use client";

import { useState } from "react";
import type { FinalResponse } from "@/lib/types";
import type { HistoryEntry } from "@/lib/useHistory";

interface Props {
  entries: HistoryEntry[];
  onPick: (entry: { query: string; final: FinalResponse }) => void;
  onClear: () => void;
  onRemove: (id: string) => void;
}

const INITIAL_VISIBLE = 5;

export function HistoryPanel({ entries, onPick, onClear, onRemove }: Props) {
  const [expanded, setExpanded] = useState(false);
  const [showAll, setShowAll] = useState(false);
  if (entries.length === 0) return null;

  const visible = showAll ? entries : entries.slice(0, INITIAL_VISIBLE);
  const hasMore = entries.length > INITIAL_VISIBLE;

  return (
    <section
      className="mt-5 bg-paper-deep/60 border border-paper-edge rounded-lg
                 overflow-hidden"
      aria-label="Riwayat kueri"
    >
      <button
        type="button"
        onClick={() => setExpanded((v) => !v)}
        className="w-full flex items-center gap-3 px-4 py-3 text-left
                   hover:bg-paper-deep transition-colors"
        aria-expanded={expanded}
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
          className={`text-ink-mid transition-transform ${expanded ? "rotate-90" : ""}`}
          aria-hidden="true"
        >
          <polyline points="9 18 15 12 9 6" />
        </svg>
        <span className="chapter-mark text-ink-mid">Riwayat</span>
        <span className="text-caption text-ink-faint font-mono">
          {entries.length} kueri
        </span>
        <span className="flex-1" />
        {expanded && (
          <span
            role="button"
            tabIndex={0}
            onClick={(e) => {
              e.stopPropagation();
              if (confirm("Hapus seluruh riwayat?")) onClear();
            }}
            onKeyDown={(e) => {
              if (e.key === "Enter" || e.key === " ") {
                e.preventDefault();
                if (confirm("Hapus seluruh riwayat?")) onClear();
              }
            }}
            className="text-caption text-ink-faint hover:text-oxblood
                       transition-colors font-mono uppercase tracking-editorial
                       cursor-pointer"
          >
            Hapus semua
          </span>
        )}
      </button>

      {expanded && (
        <ul className="divide-y divide-paper-edge border-t border-paper-edge">
          {visible.map((entry) => (
            <HistoryRow
              key={entry.id}
              entry={entry}
              onPick={() => onPick(entry)}
              onRemove={() => onRemove(entry.id)}
            />
          ))}
          {hasMore && !showAll && (
            <li className="px-4 py-2.5 bg-paper-deep/30">
              <button
                type="button"
                onClick={() => setShowAll(true)}
                className="text-caption font-mono uppercase tracking-editorial
                           text-civic hover:text-civic/80 transition-colors"
              >
                Tampilkan semua ({entries.length})
              </button>
            </li>
          )}
        </ul>
      )}
    </section>
  );
}

function HistoryRow({
  entry,
  onPick,
  onRemove,
}: {
  entry: HistoryEntry;
  onPick: () => void;
  onRemove: () => void;
}) {
  const age = formatAge(Date.now() - entry.timestamp);
  const refusal = entry.final.refusal_reason;
  const cached = entry.final.from_cache;
  return (
    <li className="group flex items-start gap-3 px-4 py-2.5 hover:bg-paper-deep transition-colors">
      <button
        type="button"
        onClick={onPick}
        className="flex-1 min-w-0 text-left"
        title="Muat ulang jawaban ini"
      >
        <div className="flex items-center gap-2 flex-wrap mb-0.5">
          {refusal ? (
            <span className="text-caption font-mono uppercase tracking-editorial text-oxblood">
              Penolakan
            </span>
          ) : (
            <span className="text-caption font-mono uppercase tracking-editorial text-civic">
              {entry.final.citations.length} kutipan
            </span>
          )}
          {cached && (
            <span className="text-caption font-mono uppercase tracking-editorial text-ink-faint">
              · cache
            </span>
          )}
          <span className="text-caption text-ink-faint font-mono">· {age}</span>
        </div>
        <p className="text-body text-ink leading-snug truncate">{entry.query}</p>
      </button>
      <button
        type="button"
        onClick={onRemove}
        className="shrink-0 text-ink-ghost hover:text-oxblood transition-colors
                   opacity-0 group-hover:opacity-100"
        aria-label="Hapus entri"
        title="Hapus entri"
      >
        <svg
          width="14"
          height="14"
          viewBox="0 0 16 16"
          fill="none"
          stroke="currentColor"
          strokeWidth="1.5"
          strokeLinecap="round"
        >
          <path d="M3 3 L13 13 M13 3 L3 13" />
        </svg>
      </button>
    </li>
  );
}

function formatAge(ms: number): string {
  const s = Math.floor(ms / 1000);
  if (s < 60) return "baru saja";
  const m = Math.floor(s / 60);
  if (m < 60) return `${m} menit lalu`;
  const h = Math.floor(m / 60);
  if (h < 24) return `${h} jam lalu`;
  const d = Math.floor(h / 24);
  return `${d} hari lalu`;
}
