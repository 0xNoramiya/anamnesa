"use client";

import { useEffect, useMemo, useRef } from "react";
import type { StreamStatus } from "@/lib/useQueryStream";
import type { TraceEvent } from "@/lib/types";

interface Props {
  events: TraceEvent[];
  status: StreamStatus;
}

/**
 * Right-hand agent-trace panel. Each event is a monospace row with a
 * coloured left rule indicating which agent emitted it. The panel is the
 * ONE thing that makes the agentic work visible to a judge — if this
 * renders nothing, the product looks like a generic chat UI.
 */
export function TraceSidebar({ events, status }: Props) {
  const bottomRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth", block: "end" });
  }, [events.length]);

  const totals = useMemo(() => {
    let tokens = 0;
    let lastMs = 0;
    for (const ev of events) {
      tokens += ev.tokens_used ?? 0;
      lastMs = Math.max(lastMs, ev.latency_ms ?? 0);
    }
    return { tokens, lastMs };
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

      <div className="flex-1 overflow-y-auto px-4 py-3 no-scrollbar">
        {events.length === 0 && <EmptyState status={status} />}
        {events.length > 0 && (
          <ol className="space-y-2">
            {events.map((ev, i) => (
              <TraceRow key={`${ev.timestamp}-${i}`} ev={ev} index={i} />
            ))}
            <div ref={bottomRef} />
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
  const label = AGENT_LABELS_ID[ev.agent] ?? ev.agent;
  const summary = summarizePayload(ev.event_type, ev.payload);
  return (
    <li
      className="trace-row animate-fade-in-up"
      data-agent={ev.agent}
      style={{ animationDelay: `${Math.min(index * 30, 420)}ms` }}
    >
      <div className="flex items-baseline gap-2">
        <span className="text-ink-ghost text-[0.66rem] tabular-nums">{ts}</span>
        <span className="text-ink font-medium uppercase tracking-wide text-[0.7rem]">
          {label}
        </span>
        <span className="text-ink-faint text-[0.7rem]">· {ev.event_type}</span>
      </div>
      {summary && (
        <div className="mt-0.5 text-ink-mid text-[0.72rem] leading-snug break-words">
          {summary}
        </div>
      )}
      {(ev.latency_ms > 0 || ev.tokens_used > 0) && (
        <div className="mt-0.5 text-ink-ghost text-[0.66rem] tabular-nums">
          {ev.latency_ms > 0 && <span>{ev.latency_ms} ms</span>}
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

function summarizePayload(
  eventType: string,
  payload: Record<string, unknown>,
): string | null {
  if (!payload || Object.keys(payload).length === 0) return null;
  // Whitelist of known fields we render inline; everything else is
  // shown compacted as "key=value · key=value".
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
  ];
  for (const k of order) {
    if (k in payload) {
      const v = payload[k];
      parts.push(`${k}=${formatVal(v)}`);
    }
  }
  if (parts.length === 0) {
    const top = Object.entries(payload).slice(0, 3);
    parts.push(
      ...top.map(([k, v]) => `${k}=${formatVal(v)}`)
    );
  }
  return parts.join(" · ");
}

function formatVal(v: unknown): string {
  if (Array.isArray(v)) return `[${v.map(String).slice(0, 4).join(", ")}${v.length > 4 ? ", …" : ""}]`;
  if (typeof v === "object" && v !== null) return JSON.stringify(v).slice(0, 40);
  return String(v);
}
