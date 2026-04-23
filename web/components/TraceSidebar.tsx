"use client";

import { useEffect, useMemo, useRef, useState } from "react";
import type { StreamStatus } from "@/lib/useQueryStream";
import type { TraceEvent } from "@/lib/types";

interface Props {
  events: TraceEvent[];
  status: StreamStatus;
}

/**
 * Right-hand agent-trace panel. Events stream in rapid-fire during a
 * Mode Agen run — a typical query produces 15-25 events across five
 * agents. Raw chronological rendering scrolls past the user and buries
 * the structure. We instead group consecutive same-agent events into
 * collapsible "phases" so the trace reads as:
 *
 *   ▸ Normalizer · 1 peristiwa · 2.7s
 *   ▸ Retriever · 1 peristiwa · 1.8s
 *   ▾ Drafter · 6 peristiwa · 61.2s
 *       [expanded rows]
 *   ▾ Verifier · 3 peristiwa · 52.9s
 *       [expanded rows]
 *
 * The LAST (current) phase is always expanded; earlier ones start
 * collapsed. User can click to toggle any phase.
 */
export function TraceSidebar({ events, status }: Props) {
  const scrollRef = useRef<HTMLDivElement>(null);

  // Scroll only the inner container — never the window. `scrollIntoView`
  // bubbles up through every scrollable ancestor, which during the
  // 60-90s Drafter phase pulls the reader's main column to the top on
  // every new trace event. Touching `scrollTop` directly isolates the
  // effect to this panel. We also skip the scroll when the user is
  // reading earlier events (i.e. they scrolled up) — detected by a
  // <120px gap from the current bottom.
  useEffect(() => {
    const el = scrollRef.current;
    if (!el) return;
    const nearBottom =
      el.scrollHeight - el.scrollTop - el.clientHeight < 120;
    if (nearBottom) {
      el.scrollTop = el.scrollHeight;
    }
  }, [events.length]);

  const groups = useMemo(() => buildGroups(events), [events]);
  const totals = useMemo(() => {
    let tokens = 0;
    for (const ev of events) tokens += ev.tokens_used ?? 0;
    return { tokens };
  }, [events]);

  return (
    <aside className="flex flex-col h-full bg-paper-deep rounded-lg border border-paper-edge">
      <header className="px-4 pt-4 pb-3 border-b border-paper-edge">
        <div className="flex items-center justify-between">
          <div className="chapter-mark">Jejak Agen</div>
          <StatusChip status={status} />
        </div>
        <p className="mt-1.5 text-caption text-ink-faint leading-snug">
          Normalizer → Retriever → Drafter → Verifier
        </p>
      </header>

      <div
        ref={scrollRef}
        className="flex-1 overflow-y-auto px-4 py-3 no-scrollbar"
      >
        {events.length === 0 && <EmptyState status={status} />}
        {events.length > 0 && (
          <ol className="space-y-2.5">
            {groups.map((g, i) => (
              <PhaseGroup
                key={`${g.agent}-${g.startIdx}`}
                group={g}
                isLast={i === groups.length - 1}
              />
            ))}
          </ol>
        )}
      </div>

      <footer className="px-4 py-2.5 border-t border-paper-edge grid grid-cols-2 gap-3 text-[0.7rem] font-mono uppercase tracking-editorial text-ink-faint">
        <div>
          <div>Events</div>
          <div className="text-ink font-semibold mt-0.5 text-sm">{events.length}</div>
        </div>
        <div>
          <div>Tokens</div>
          <div className="text-ink font-semibold mt-0.5 text-sm">
            {totals.tokens.toLocaleString()}
          </div>
        </div>
      </footer>
    </aside>
  );
}

interface PhaseGroupData {
  agent: string;
  events: TraceEvent[];
  startIdx: number;
  totalLatencyMs: number;
  totalTokens: number;
}

function buildGroups(events: TraceEvent[]): PhaseGroupData[] {
  const groups: PhaseGroupData[] = [];
  let current: PhaseGroupData | null = null;
  events.forEach((ev, i) => {
    if (current && current.agent === ev.agent) {
      current.events.push(ev);
      current.totalLatencyMs += ev.latency_ms ?? 0;
      current.totalTokens += ev.tokens_used ?? 0;
    } else {
      current = {
        agent: ev.agent,
        events: [ev],
        startIdx: i,
        totalLatencyMs: ev.latency_ms ?? 0,
        totalTokens: ev.tokens_used ?? 0,
      };
      groups.push(current);
    }
  });
  return groups;
}

function PhaseGroup({
  group,
  isLast,
}: {
  group: PhaseGroupData;
  isLast: boolean;
}) {
  // Current phase always expanded; earlier ones start collapsed. User
  // can toggle either way.
  const [expanded, setExpanded] = useState(isLast);
  // Keep the last group in sync if more events land on the same agent.
  useEffect(() => {
    if (isLast) setExpanded(true);
  }, [isLast]);

  const label = AGENT_LABELS_ID[group.agent] ?? group.agent;
  const eventWord = group.events.length === 1 ? "peristiwa" : "peristiwa";

  return (
    <li
      className="animate-fade-in-up"
      data-agent={group.agent}
      style={{ animationDelay: `${Math.min(group.startIdx * 30, 420)}ms` }}
    >
      <button
        type="button"
        onClick={() => setExpanded((v) => !v)}
        className="w-full text-left px-2.5 py-1.5 rounded-md
                   bg-white border border-paper-edge
                   hover:border-civic/30 transition-colors
                   flex items-center gap-2"
        aria-expanded={expanded}
        data-agent={group.agent}
      >
        <span
          className="inline-block w-2 h-5 rounded-sm shrink-0"
          style={{ background: AGENT_COLOR[group.agent] ?? "#9ca3af" }}
        />
        <svg
          width="10"
          height="10"
          viewBox="0 0 24 24"
          fill="none"
          stroke="currentColor"
          strokeWidth="2.5"
          strokeLinecap="round"
          strokeLinejoin="round"
          className={`text-ink-ghost transition-transform ${expanded ? "rotate-90" : ""}`}
          aria-hidden="true"
        >
          <polyline points="9 18 15 12 9 6" />
        </svg>
        <span className="font-mono text-[0.76rem] font-semibold text-ink uppercase tracking-editorial">
          {label}
        </span>
        <span className="ml-auto flex items-center gap-2 text-[0.68rem] font-mono text-ink-faint tabular-nums">
          <span>{group.events.length} {eventWord}</span>
          {group.totalLatencyMs > 0 && (
            <>
              <span className="text-ink-ghost">·</span>
              <span>{formatDuration(group.totalLatencyMs)}</span>
            </>
          )}
        </span>
      </button>

      {expanded && (
        <ol className="mt-1.5 space-y-1.5 pl-2.5 border-l-2 border-paper-edge ml-1.5">
          {group.events.map((ev, i) => (
            <TraceRow
              key={`${ev.timestamp}-${i}`}
              ev={ev}
              index={group.startIdx + i}
            />
          ))}
        </ol>
      )}
    </li>
  );
}

function StatusChip({ status }: { status: StreamStatus }) {
  const label =
    status === "idle" ? "Siap" :
    status === "submitting" ? "Memulai" :
    status === "streaming" ? "Berjalan" :
    status === "done" ? "Selesai" :
    "Error";
  const tone =
    status === "streaming" ? "badge-aging" :
    status === "done"      ? "badge-current" :
    status === "error"     ? "badge-superseded" :
                             "badge-unknown";
  return (
    <span className={`badge ${tone}`}>
      {status === "streaming" && (
        <span className="inline-block w-1.5 h-1.5 rounded-full bg-amber animate-pulse" />
      )}
      {label}
    </span>
  );
}

function EmptyState({ status }: { status: StreamStatus }) {
  return (
    <div className="py-6 flex flex-col items-start gap-2 text-ink-faint">
      <div className="font-mono text-[0.7rem] uppercase tracking-editorial">
        Menunggu kueri…
      </div>
      <p className="text-caption leading-relaxed max-w-[34ch]">
        Ketik satu pertanyaan klinis. Anamnesa menampilkan setiap langkah
        agen di sini, real time.
      </p>
      {status === "submitting" && (
        <div className="text-caption text-civic font-mono mt-1">
          → membangun permintaan…
        </div>
      )}
    </div>
  );
}

function TraceRow({ ev, index }: { ev: TraceEvent; index: number }) {
  const ts = formatTs(ev.timestamp);
  const summary = summarizePayload(ev.event_type, ev.payload);
  return (
    <li
      className="trace-row animate-fade-in-up"
      data-agent={ev.agent}
      style={{ animationDelay: `${Math.min(index * 30, 420)}ms` }}
    >
      <div className="flex items-baseline gap-2">
        <span className="text-ink-ghost text-[0.66rem] tabular-nums">{ts}</span>
        <span className="text-ink-faint text-[0.7rem]">{ev.event_type}</span>
      </div>
      {summary && (
        <div className="mt-0.5 text-ink-mid text-[0.72rem] leading-snug break-words">
          {summary}
        </div>
      )}
      {(ev.latency_ms > 0 || ev.tokens_used > 0) && (
        <div className="mt-0.5 text-ink-ghost text-[0.66rem] tabular-nums">
          {ev.latency_ms > 0 && <span>{formatDuration(ev.latency_ms)}</span>}
          {ev.latency_ms > 0 && ev.tokens_used > 0 && <span> · </span>}
          {ev.tokens_used > 0 && <span>{ev.tokens_used.toLocaleString()} tok</span>}
        </div>
      )}
    </li>
  );
}

const AGENT_LABELS_ID: Record<string, string> = {
  orchestrator: "Orkestrator",
  normalizer:   "Normalizer",
  retriever:    "Retriever",
  drafter:      "Drafter",
  verifier:     "Verifier",
};

// Must match the box-shadow colors in globals.css `.trace-row[data-agent]`
// so the phase-group swatch and its inner rows read as one unit.
const AGENT_COLOR: Record<string, string> = {
  normalizer:   "#1e40af",  // civic
  retriever:    "#2e7d5b",  // sage
  drafter:      "#b45309",  // amber
  verifier:     "#991b1b",  // oxblood
  orchestrator: "#6b7280",  // ink-ghost
};

function formatTs(iso: string): string {
  try {
    const d = new Date(iso);
    return d.toLocaleTimeString("id-ID", {
      hour: "2-digit",
      minute: "2-digit",
      second: "2-digit",
      hour12: false,
    });
  } catch {
    return iso.slice(11, 19);
  }
}

function formatDuration(ms: number): string {
  if (ms < 1000) return `${ms} ms`;
  if (ms < 60_000) return `${(ms / 1000).toFixed(1)}s`;
  const m = Math.floor(ms / 60_000);
  const s = Math.round((ms % 60_000) / 1000);
  return `${m}m ${s.toString().padStart(2, "0")}s`;
}

function summarizePayload(
  eventType: string,
  payload: Record<string, unknown>,
): string | null {
  if (!payload || Object.keys(payload).length === 0) return null;
  const parts: string[] = [];
  const order = [
    "reason",
    "intent",
    "condition_tags",
    "patient_context",
    "attempt",
    "chunks",
    "citations",
    "claims",
    "tool",
    "decision",
    "supported",
    "unsupported",
    "has_unsupported",
    "wall_clock_ms",
    "total_tokens",
    "refusal_reason",
    "iteration",
    "returned_chunks",
    "query",
    "doc_id",
    "age_s",
  ];
  for (const k of order) {
    if (k in payload) {
      const v = payload[k];
      parts.push(`${k}=${formatVal(v)}`);
    }
  }
  if (parts.length === 0) {
    const top = Object.entries(payload).slice(0, 3);
    parts.push(...top.map(([k, v]) => `${k}=${formatVal(v)}`));
  }
  return parts.join(" · ");
}

function formatVal(v: unknown): string {
  if (Array.isArray(v)) return `[${v.map(String).slice(0, 4).join(", ")}${v.length > 4 ? ", …" : ""}]`;
  if (typeof v === "object" && v !== null) return JSON.stringify(v).slice(0, 40);
  if (typeof v === "string" && v.length > 48) return v.slice(0, 47) + "…";
  return String(v);
}
