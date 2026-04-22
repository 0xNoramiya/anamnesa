"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { Masthead } from "@/components/Masthead";
import { QueryInput } from "@/components/QueryInput";
import { AnswerPanel } from "@/components/AnswerPanel";
import { HistoryPanel } from "@/components/HistoryPanel";
import { TraceSidebar } from "@/components/TraceSidebar";
import { PdfViewer } from "@/components/PdfViewer";
import { FastSearch } from "@/components/FastSearch";
import { useQueryStream } from "@/lib/useQueryStream";
import { useHistory } from "@/lib/useHistory";
import type { FinalResponse, TraceEvent } from "@/lib/types";

type Mode = "fast" | "agentic";
interface PdfOpen { docId: string; page: number }

export default function HomePage() {
  const stream = useQueryStream();
  const history = useHistory();
  const [mode, setMode] = useState<Mode>("fast");
  const [pdf, setPdf] = useState<PdfOpen | null>(null);
  // Track the query text that produced the currently-visible answer so
  // the history entry carries the right label. Reset on fresh submit.
  const currentQueryRef = useRef<string>("");
  const savedFinalRef = useRef<FinalResponse | null>(null);

  const openPdf = useCallback(
    (docId: string, page: number) => setPdf({ docId, page }),
    [],
  );
  const closePdf = useCallback(() => setPdf(null), []);

  const submitAgentic = useCallback(
    (q: string) => {
      currentQueryRef.current = q;
      savedFinalRef.current = null;
      stream.submit(q);
    },
    [stream],
  );

  // Persist to history when a new final lands. Guard via ref so a
  // re-render with the same `final` doesn't double-save.
  useEffect(() => {
    const fin = stream.final;
    if (!fin) return;
    if (savedFinalRef.current === fin) return;
    savedFinalRef.current = fin;
    if (currentQueryRef.current) {
      history.addEntry(currentQueryRef.current, fin);
    }
  }, [stream.final, history]);

  const loadHistoryEntry = useCallback(
    (entry: { query: string; final: FinalResponse }) => {
      currentQueryRef.current = entry.query;
      savedFinalRef.current = entry.final;
      stream.loadFromHistory(entry.final);
      setMode("agentic");
    },
    [stream],
  );

  // Escalate from Fast → Agentic with the current query pre-filled.
  const escalate = useCallback((q: string) => {
    setMode("agentic");
    // Defer one tick so the agentic UI mounts + takes the submit call.
    setTimeout(() => submitAgentic(q), 0);
  }, [submitAgentic]);

  return (
    <main className="min-h-screen">
      <div className="mx-auto max-w-[1440px] px-6 lg:px-10">
        <Masthead />
        <ModeTabs mode={mode} onChange={setMode} />

        {mode === "fast" && (
          <div className="grid grid-cols-12 gap-8 pt-6 pb-16">
            <section className="col-span-12 lg:col-span-9">
              <FastSearch onOpenPdf={openPdf} onEscalate={escalate} />
            </section>
            <aside className="col-span-12 lg:col-span-3">
              <FastSearchHint />
            </aside>
          </div>
        )}

        {mode === "agentic" && (
          <div className="grid grid-cols-12 gap-8 pt-6 pb-16">
            <section className="col-span-12 lg:col-span-8">
              <QueryInput onSubmit={submitAgentic} status={stream.status} />

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
                  <AnswerPanel final={stream.final} onOpenPdf={openPdf} />
                </div>
              )}

              {stream.status === "streaming" && !stream.final && (
                <ThinkingIndicator events={stream.events} />
              )}
            </section>

            <section
              className="col-span-12 lg:col-span-4
                         lg:sticky lg:top-6 lg:self-start
                         lg:max-h-[calc(100vh-2rem)]"
            >
              <TraceSidebar events={stream.events} status={stream.status} />
            </section>
          </div>
        )}
      </div>
      <PdfViewer
        docId={pdf?.docId ?? null}
        page={pdf?.page ?? 1}
        onClose={closePdf}
      />
    </main>
  );
}

function ModeTabs({ mode, onChange }: { mode: Mode; onChange: (m: Mode) => void }) {
  return (
    <nav className="pt-5 flex items-center gap-1 border-b border-paper-edge -mb-px">
      <TabButton active={mode === "fast"} onClick={() => onChange("fast")}>
        Cari Cepat
        <span className="ml-2 text-caption text-ink-faint font-normal normal-case">
          retrieval saja
        </span>
      </TabButton>
      <TabButton active={mode === "agentic"} onClick={() => onChange("agentic")}>
        Mode Agen
        <span className="ml-2 text-caption text-ink-faint font-normal normal-case">
          dengan sintesis + verifikasi
        </span>
      </TabButton>
    </nav>
  );
}

function TabButton({
  active,
  onClick,
  children,
}: {
  active: boolean;
  onClick: () => void;
  children: React.ReactNode;
}) {
  return (
    <button
      type="button"
      onClick={onClick}
      className={`px-4 py-2.5 text-body font-medium uppercase tracking-[0.04em]
                  text-[0.82rem] border-b-2 -mb-px transition-colors
                  ${
                    active
                      ? "border-civic text-civic"
                      : "border-transparent text-ink-faint hover:text-ink-mid"
                  }`}
    >
      {children}
    </button>
  );
}

function FastSearchHint() {
  return (
    <div className="bg-paper-deep border border-paper-edge rounded-lg p-4">
      <div className="chapter-mark mb-2">Tentang Cari Cepat</div>
      <p className="text-body leading-relaxed text-ink-mid">
        Pencarian hybrid BM25 + embedding multibahasa (BGE-M3) langsung
        pada 2.461 bagian pedoman Indonesia yang terindeks.
      </p>
      <p className="mt-3 text-caption text-ink-faint leading-relaxed">
        Tidak ada LLM yang dipanggil di mode ini — hasil langsung dari
        indeks. Gunakan <strong className="text-ink">Mode Agen</strong>{" "}
        bila Anda butuh ringkasan terverifikasi dengan bendera keberlakuan.
      </p>
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
  // The retriever often runs silently inside the drafter tool-use loop;
  // treat "drafter active" as implicit confirmation retrieval happened.
  if (agentsSeen.has("drafter")) agentsSeen.add("retriever");

  const elapsedMs = now - startedAt;
  const elapsed = formatElapsed(elapsedMs);
  // Soft progress sense: map elapsed seconds to a percentage that creeps
  // toward 95% around the 4-minute mark but never reaches 100 — actual
  // completion is signalled by the status transition, not this bar.
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
          Opus 4.7 (mode xhigh effort) biasanya memerlukan 2–4 menit untuk
          kueri klinis yang kompleks. Jejak agen di sebelah kanan
          menampilkan setiap keputusan saat terjadi.
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
