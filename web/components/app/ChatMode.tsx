"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { QueryInput } from "@/components/QueryInput";
import { AnswerPanel } from "@/components/AnswerPanel";
import { HistoryPanel } from "@/components/HistoryPanel";
import { TraceSidebar } from "@/components/TraceSidebar";
import { PdfViewer } from "@/components/PdfViewer";
import { RetrievalPreview } from "@/components/app/RetrievalPreview";
import { useQueryStream } from "@/lib/useQueryStream";
import { useHistory } from "@/lib/useHistory";
import type { FinalResponse, TraceEvent } from "@/lib/types";

interface PdfOpen { docId: string; page: number }

/**
 * Chat / Mode Agen — the existing agentic surface, lifted out of the
 * original root page.tsx and nested into the new sidebar shell at
 * /chat. Keeps all previously-shipped behavior (history, cache,
 * cite hover, PDF modal, thinking indicator) so behavior doesn't
 * regress during the redesign.
 */
export function ChatMode() {
  const stream = useQueryStream();
  const history = useHistory();
  const [pdf, setPdf] = useState<PdfOpen | null>(null);

  const currentQueryRef = useRef<string>("");
  const savedFinalRef = useRef<FinalResponse | null>(null);

  const openPdf = useCallback(
    (docId: string, page: number) => setPdf({ docId, page }),
    [],
  );
  const closePdf = useCallback(() => setPdf(null), []);

  const submit = useCallback(
    (q: string) => {
      currentQueryRef.current = q;
      savedFinalRef.current = null;
      stream.submit(q);
    },
    [stream],
  );

  useEffect(() => {
    const fin = stream.final;
    if (!fin) return;
    if (savedFinalRef.current === fin) return;
    savedFinalRef.current = fin;
    if (currentQueryRef.current) {
      history.addEntry(currentQueryRef.current, fin);
    }
  }, [stream.final, history]);

  // Pick up a handed-off query from /pencarian's "Coba Mode Agen →"
  // button OR a restored entry from /riwayat. sessionStorage keeps
  // both simple and works across the client-side route transition.
  useEffect(() => {
    try {
      const restore = window.sessionStorage.getItem("anamnesa.restore_entry");
      if (restore) {
        window.sessionStorage.removeItem("anamnesa.restore_entry");
        const entry = JSON.parse(restore) as { query: string; final: FinalResponse };
        currentQueryRef.current = entry.query;
        savedFinalRef.current = entry.final;
        stream.loadFromHistory(entry.final);
        return;
      }
      const prefill = window.sessionStorage.getItem("anamnesa.prefill_query");
      if (prefill) {
        window.sessionStorage.removeItem("anamnesa.prefill_query");
        submit(prefill);
      }
    } catch {
      // soft-fail
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const loadHistoryEntry = useCallback(
    (entry: { query: string; final: FinalResponse }) => {
      currentQueryRef.current = entry.query;
      savedFinalRef.current = entry.final;
      stream.loadFromHistory(entry.final);
    },
    [stream],
  );

  return (
    <div className="mx-auto max-w-[1440px] px-4 md:px-6 lg:px-10 py-4 md:py-8">
      <div className="grid grid-cols-12 gap-4 md:gap-6 pb-10">
        <section className="col-span-12 lg:col-span-8 min-w-0">
          <QueryInput onSubmit={submit} status={stream.status} />

          {history.entries.length > 0 && (
            <HistoryPanel
              entries={history.entries}
              onPick={loadHistoryEntry}
              onClear={history.clearAll}
              onRemove={history.removeEntry}
            />
          )}

          {stream.status === "error" && stream.error && (
            <div className="mt-8 bg-oxblood/5 border border-oxblood/20 rounded-lg p-4 text-body">
              <div className="chapter-mark text-oxblood mb-1">Error</div>
              <pre className="font-mono text-caption whitespace-pre-wrap text-ink-mid">
                {stream.error}
              </pre>
            </div>
          )}

          {stream.final && (
            <div className="mt-10">
              <AnswerPanel
                final={stream.final}
                queryText={currentQueryRef.current}
                onOpenPdf={openPdf}
              />
            </div>
          )}

          {stream.status === "streaming" && !stream.final && (
            <>
              <ThinkingIndicator events={stream.events} />
              <RetrievalPreview events={stream.events} onOpenPdf={openPdf} />
            </>
          )}
        </section>

        {/* Trace sidebar: desktop shows it inline; mobile hides it
            (users can switch to /agent-track to inspect). */}
        <section
          className="hidden lg:block lg:col-span-4
                     lg:sticky lg:top-6 lg:self-start
                     lg:max-h-[calc(100vh-2rem)]"
        >
          <TraceSidebar events={stream.events} status={stream.status} />
        </section>
      </div>
      <PdfViewer
        docId={pdf?.docId ?? null}
        page={pdf?.page ?? 1}
        onClose={closePdf}
      />
    </div>
  );
}

const PHASE_ORDER: TraceEvent["agent"][] = [
  "orchestrator",
  "normalizer",
  "retriever",
  "drafter",
  "verifier",
];

const PHASE_LABELS: Record<TraceEvent["agent"], string> = {
  orchestrator: "Memulai",
  normalizer: "Normalisasi kueri",
  retriever: "Mencari di pedoman",
  drafter: "Menyusun jawaban",
  verifier: "Memverifikasi kutipan",
};

function formatElapsed(ms: number): string {
  const s = Math.floor(ms / 1000);
  const mm = Math.floor(s / 60);
  const ss = s % 60;
  return `${mm}:${ss.toString().padStart(2, "0")}`;
}

function ThinkingIndicator({ events }: { events: TraceEvent[] }) {
  const [startedAt] = useState(() => Date.now());
  const [now, setNow] = useState(() => Date.now());

  useEffect(() => {
    const t = window.setInterval(() => setNow(Date.now()), 1000);
    return () => window.clearInterval(t);
  }, []);

  const latest = events.length > 0 ? events[events.length - 1] : null;
  const currentAgent: TraceEvent["agent"] = latest?.agent ?? "orchestrator";
  const agentsSeen = new Set(events.map((e) => e.agent));
  if (agentsSeen.has("drafter")) agentsSeen.add("retriever");

  const elapsedMs = now - startedAt;
  const elapsed = formatElapsed(elapsedMs);
  const pct = Math.min(95, Math.round((1 - Math.exp(-elapsedMs / 90000)) * 100));

  return (
    <div className="mt-10 animate-fade-in-up">
      <div className="flex items-center gap-3 mb-3">
        <span className="chapter-mark text-civic">Memproses</span>
        <span className="flex-1 h-px bg-paper-edge" />
        <span className="font-mono text-caption text-ink-mid tabular-nums">
          {elapsed}
        </span>
      </div>

      <div className="bg-civic/5 border border-civic/20 rounded-lg p-4">
        <div className="flex items-baseline justify-between gap-3">
          <p className="text-body-lg text-ink font-medium">
            {PHASE_LABELS[currentAgent]}
            <span className="ml-2 inline-flex gap-1 align-middle">
              <span className="w-1.5 h-1.5 rounded-full bg-civic animate-pulse" />
              <span className="w-1.5 h-1.5 rounded-full bg-civic animate-pulse [animation-delay:150ms]" />
              <span className="w-1.5 h-1.5 rounded-full bg-civic animate-pulse [animation-delay:300ms]" />
            </span>
          </p>
          <span className="font-mono text-caption text-ink-mid tabular-nums shrink-0">
            {events.length} peristiwa
          </span>
        </div>

        <div className="mt-3 h-1 bg-civic/10 rounded-full overflow-hidden">
          <div
            className="h-full bg-civic/70 transition-[width] duration-1000 ease-out"
            style={{ width: `${pct}%` }}
          />
        </div>

        <ol className="mt-4 flex flex-wrap gap-x-3 gap-y-1.5 text-caption">
          {PHASE_ORDER.filter((a) => a !== "orchestrator").map((agent) => {
            const active = agent === currentAgent;
            const done = agentsSeen.has(agent) && !active;
            return (
              <li
                key={agent}
                className="flex items-center gap-1.5 font-mono uppercase tracking-editorial"
              >
                <PhaseDot state={active ? "active" : done ? "done" : "pending"} />
                <span
                  className={
                    active
                      ? "text-civic"
                      : done
                        ? "text-ink-mid"
                        : "text-ink-faint"
                  }
                >
                  {PHASE_LABELS[agent]}
                </span>
              </li>
            );
          })}
        </ol>

        <p className="mt-4 text-caption text-ink-faint max-w-[58ch] leading-relaxed">
          Opus 4.7 (mode high effort) biasanya memerlukan ~2 menit untuk
          kueri klinis yang kompleks. Jejak agen di sebelah kanan menampilkan
          setiap keputusan saat terjadi.
        </p>
      </div>
    </div>
  );
}

function PhaseDot({ state }: { state: "done" | "active" | "pending" }) {
  if (state === "active") {
    return (
      <span className="relative inline-flex w-2 h-2">
        <span className="absolute inset-0 rounded-full bg-civic/30 animate-ping" />
        <span className="relative inline-block w-2 h-2 rounded-full bg-civic" />
      </span>
    );
  }
  if (state === "done") {
    return <span className="inline-block w-2 h-2 rounded-full bg-civic/60" />;
  }
  return <span className="inline-block w-2 h-2 rounded-full border border-paper-edge bg-white" />;
}
