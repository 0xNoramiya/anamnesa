"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { QueryInput } from "@/components/QueryInput";
import { AnswerPanel } from "@/components/AnswerPanel";
import { TraceSidebar } from "@/components/TraceSidebar";
import { PdfViewer } from "@/components/PdfViewer";
import { RetrievalPreview } from "@/components/app/RetrievalPreview";
import { StreamingAnswer } from "@/components/app/StreamingAnswer";
import { useQueryStream } from "@/lib/useQueryStream";
import { useHistory } from "@/lib/useHistory";
import type { FinalResponse, TraceEvent } from "@/lib/types";

interface PdfOpen { docId: string; page: number }

interface Turn { query: string; final: FinalResponse }

/** localStorage persistence for the chat thread. A shipped multi-turn
 *  feature that forgets its conversation on page refresh is fragile —
 *  one accidental reload and the context is gone. We persist a capped
 *  tail of the thread plus a savedAt timestamp; restoration expires
 *  after THREAD_TTL_MS so coming back the next day doesn't silently
 *  chain an unrelated new question onto yesterday's DBD discussion. */
const THREAD_STORAGE_KEY = "anamnesa.chat_thread";
const THREAD_MAX_TURNS = 5;
const THREAD_TTL_MS = 24 * 60 * 60 * 1000; // 24 hours

interface PersistedThread {
  thread: Turn[];
  savedAt: number;
}

function loadPersistedThread(): Turn[] | null {
  try {
    const raw = window.localStorage.getItem(THREAD_STORAGE_KEY);
    if (!raw) return null;
    const parsed = JSON.parse(raw) as PersistedThread;
    if (!parsed || !Array.isArray(parsed.thread) || parsed.thread.length === 0) {
      return null;
    }
    if (typeof parsed.savedAt !== "number" ||
        Date.now() - parsed.savedAt > THREAD_TTL_MS) {
      window.localStorage.removeItem(THREAD_STORAGE_KEY);
      return null;
    }
    return parsed.thread;
  } catch {
    return null;
  }
}

function savePersistedThread(thread: Turn[]): void {
  try {
    if (thread.length === 0) {
      window.localStorage.removeItem(THREAD_STORAGE_KEY);
      return;
    }
    const payload: PersistedThread = {
      thread: thread.slice(-THREAD_MAX_TURNS),
      savedAt: Date.now(),
    };
    window.localStorage.setItem(THREAD_STORAGE_KEY, JSON.stringify(payload));
  } catch {
    // Quota or disabled — soft-fail; the feature is still usable in-memory.
  }
}

/** Plain-text excerpt of an answer to ship to the backend on the next
 *  turn. Strips Markdown citation markers + asterisk bolding and caps at
 *  1200 chars so the Normalizer gets a gist, not a wall. Keeps the first
 *  two paragraphs because the Drafter is taught to front-load the
 *  direct recommendation. */
function answerExcerpt(md: string): string {
  if (!md) return "";
  const stripped = md
    .replace(/\[\[[^\]]+\]\]/g, "")
    .replace(/\*\*/g, "")
    .replace(/^#{1,6}\s+/gm, "");
  const paras = stripped.split(/\n{2,}/).filter((p) => p.trim().length > 0);
  const head = paras.slice(0, 2).join("\n\n");
  return head.slice(0, 1200).trim();
}

/**
 * Chat / Mode Agen — threaded multi-turn surface.
 *
 * Queries accumulate as a conversation. Each new submit passes the most
 * recent (query, answer excerpt) to the backend; the Normalizer reads
 * both and condenses a terse follow-up like "dan kalau anak?" into a
 * standalone clinical query before retrieval.
 *
 * The in-flight turn renders via the streaming surfaces; completed turns
 * render in the thread above. A "Percakapan baru" button clears the
 * thread for a fresh start.
 */
export function ChatMode() {
  const stream = useQueryStream();
  const history = useHistory();
  const [pdf, setPdf] = useState<PdfOpen | null>(null);
  const [thread, setThread] = useState<Turn[]>([]);

  const currentQueryRef = useRef<string>("");
  const savedFinalRef = useRef<FinalResponse | null>(null);
  const threadEndRef = useRef<HTMLDivElement | null>(null);
  // Block the persistence effect from firing on mount before the
  // localStorage load completes — otherwise the initial empty `[]`
  // would write through and clear the saved thread.
  const hydratedRef = useRef(false);
  // True only when the thread was rehydrated from localStorage on
  // mount. Drives the "melanjutkan percakapan" banner; auto-clears
  // once the user submits another turn or hits reset.
  const [restoredFromSession, setRestoredFromSession] = useState(false);

  const openPdf = useCallback(
    (docId: string, page: number) => setPdf({ docId, page }),
    [],
  );
  const closePdf = useCallback(() => setPdf(null), []);

  const submit = useCallback(
    (q: string) => {
      currentQueryRef.current = q;
      savedFinalRef.current = null;
      const last = thread[thread.length - 1];
      const priorTurn = last
        ? { query: last.query, answer: answerExcerpt(last.final.answer_markdown) }
        : null;
      stream.submit(q, priorTurn);
    },
    [stream, thread],
  );

  // When a `final` lands, move it into the thread and reset the stream
  // so the input box is ready for the next follow-up.
  useEffect(() => {
    const fin = stream.final;
    if (!fin) return;
    if (savedFinalRef.current === fin) return;
    savedFinalRef.current = fin;
    const q = currentQueryRef.current;
    if (q) {
      history.addEntry(q, fin);
      setThread((prev) => [...prev, { query: q, final: fin }]);
      // User is actively engaging again — banner has served its purpose.
      setRestoredFromSession(false);
    }
  }, [stream.final, history]);

  // Auto-scroll to the latest turn when the thread grows.
  useEffect(() => {
    threadEndRef.current?.scrollIntoView({ behavior: "smooth", block: "start" });
  }, [thread.length]);

  // Persist thread to localStorage whenever it changes. Skip the first
  // render — the mount-time load effect runs after this one and would
  // see an empty localStorage if we wrote through on the initial `[]`.
  useEffect(() => {
    if (!hydratedRef.current) return;
    savePersistedThread(thread);
  }, [thread]);

  const resetConversation = useCallback(() => {
    setThread([]);
    stream.reset();
    currentQueryRef.current = "";
    savedFinalRef.current = null;
    setRestoredFromSession(false);
    try {
      window.localStorage.removeItem(THREAD_STORAGE_KEY);
    } catch {
      // soft-fail
    }
  }, [stream]);

  // Pick up a handed-off query from /pencarian's "Coba Mode Agen →"
  // button OR a restored entry from /riwayat. sessionStorage keeps
  // both simple and works across the client-side route transition.
  // Priority: sessionStorage handoff > localStorage thread restore.
  // The handoff represents explicit user intent; the localStorage
  // restore is silent continuity.
  useEffect(() => {
    try {
      const restore = window.sessionStorage.getItem("anamnesa.restore_entry");
      if (restore) {
        window.sessionStorage.removeItem("anamnesa.restore_entry");
        const entry = JSON.parse(restore) as { query: string; final: FinalResponse };
        currentQueryRef.current = entry.query;
        savedFinalRef.current = entry.final;
        setThread([{ query: entry.query, final: entry.final }]);
        stream.loadFromHistory(entry.final);
        return;
      }
      const prefill = window.sessionStorage.getItem("anamnesa.prefill_query");
      if (prefill) {
        window.sessionStorage.removeItem("anamnesa.prefill_query");
        submit(prefill);
        return;
      }
      const persisted = loadPersistedThread();
      if (persisted && persisted.length > 0) {
        const last = persisted[persisted.length - 1];
        currentQueryRef.current = last.query;
        savedFinalRef.current = last.final;
        setThread(persisted);
        setRestoredFromSession(true);
      }
    } catch {
      // soft-fail
    } finally {
      hydratedRef.current = true;
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const inFlight = stream.status === "submitting" || stream.status === "streaming";
  const hasThread = thread.length > 0;
  const isFollowUp = hasThread && !inFlight && !stream.final;
  // Guard against rendering the same final twice (once from stream.final,
  // once from the thread entry it was just moved into).
  const streamFinalAlreadyInThread =
    stream.final !== null &&
    thread.length > 0 &&
    thread[thread.length - 1].final === stream.final;

  return (
    <div className="mx-auto max-w-[1440px] px-4 md:px-6 lg:px-10 py-4 md:py-8">
      <div className="grid grid-cols-12 gap-4 md:gap-6 pb-10">
        <section className="col-span-12 lg:col-span-8 min-w-0">
          {/* Restored-session banner — the persistence feature is a quiet
              localStorage restore, so we surface a subtle indicator so
              users recognise they're resuming an earlier thread rather
              than seeing stale content in an unexpected place. */}
          {restoredFromSession && hasThread && (
            <RestoredBanner
              turnCount={thread.length}
              onDismiss={() => setRestoredFromSession(false)}
              onReset={resetConversation}
              disabled={inFlight}
            />
          )}
          {/* Thread header — only visible once a conversation is underway. */}
          {hasThread && (
            <div
              className="mb-6 flex items-center justify-between gap-3"
              style={{
                paddingBottom: 12,
                borderBottom: "1px solid var(--rule)",
              }}
            >
              <div
                className="mono"
                style={{
                  fontSize: 11,
                  color: "var(--ink-3)",
                  letterSpacing: "0.12em",
                  textTransform: "uppercase",
                }}
              >
                Percakapan · {thread.length}{" "}
                {thread.length === 1 ? "giliran" : "giliran"}
              </div>
              <button
                type="button"
                onClick={resetConversation}
                disabled={inFlight}
                className="mono"
                style={{
                  fontSize: 11,
                  color: "var(--ink-3)",
                  letterSpacing: "0.08em",
                  textTransform: "uppercase",
                  border: "1px solid var(--rule)",
                  background: "var(--paper)",
                  padding: "5px 10px",
                  borderRadius: 2,
                  cursor: inFlight ? "not-allowed" : "pointer",
                  opacity: inFlight ? 0.5 : 1,
                }}
                title="Mulai percakapan baru"
              >
                + Percakapan baru
              </button>
            </div>
          )}

          {/* Render completed thread turns. */}
          {thread.map((turn, i) => (
            <article key={i} className={i === 0 ? "" : "mt-12"}>
              <TurnQueryLine text={turn.query} index={i} />
              <div className="mt-4">
                <AnswerPanel
                  final={turn.final}
                  queryText={turn.query}
                  onOpenPdf={openPdf}
                />
              </div>
            </article>
          ))}

          {/* In-flight user query + streaming surfaces. */}
          {inFlight && currentQueryRef.current && (
            <article className={hasThread ? "mt-12" : "mt-6"}>
              <TurnQueryLine
                text={currentQueryRef.current}
                index={thread.length}
                pending
              />
              {!stream.final && (
                <div className="mt-4">
                  <ThinkingIndicator events={stream.events} />
                  <RetrievalPreview events={stream.events} onOpenPdf={openPdf} />
                  <StreamingAnswer events={stream.events} />
                </div>
              )}
              {stream.final && !streamFinalAlreadyInThread && (
                <div className="mt-4">
                  <AnswerPanel
                    final={stream.final}
                    queryText={currentQueryRef.current}
                    onOpenPdf={openPdf}
                  />
                </div>
              )}
            </article>
          )}

          <div ref={threadEndRef} />

          {stream.status === "error" && stream.error && (
            <div className="mt-8 bg-oxblood/5 border border-oxblood/20 rounded-lg p-4 text-body">
              <div className="chapter-mark text-oxblood mb-1">Error</div>
              <pre className="font-mono text-caption whitespace-pre-wrap text-ink-mid">
                {stream.error}
              </pre>
            </div>
          )}

          {/* Input stays at the bottom. In follow-up mode the label +
              placeholder reflect that Anamnesa remembers prior turns. */}
          <div className={hasThread ? "mt-10" : ""}>
            <QueryInput
              onSubmit={submit}
              status={stream.status}
              followUp={isFollowUp}
            />
          </div>
        </section>

        {/* Trace sidebar: desktop shows it inline; mobile hides it
            (users can switch to /agent-track to inspect). Sticky
            offset clears the 64px TopBar + 12px breathing room. */}
        <section
          className="hidden lg:block lg:col-span-4
                     lg:sticky lg:top-[76px] lg:self-start
                     lg:max-h-[calc(100vh-96px)]"
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

/** Subtle banner shown above the thread when the conversation was
 *  restored from localStorage on page load. Auto-dismisses when the
 *  user submits a new turn (via the stream.final effect in ChatMode)
 *  or clicks the close button. */
function RestoredBanner({
  turnCount,
  onDismiss,
  onReset,
  disabled,
}: {
  turnCount: number;
  onDismiss: () => void;
  onReset: () => void;
  disabled: boolean;
}) {
  return (
    <div
      style={{
        marginBottom: 18,
        padding: "10px 14px",
        background: "var(--paper-2)",
        border: "1px solid var(--rule)",
        borderLeft: "2px solid var(--navy, #1a2550)",
        borderRadius: 2,
        display: "flex",
        alignItems: "center",
        gap: 12,
        flexWrap: "wrap",
      }}
      role="status"
    >
      <span
        className="mono"
        style={{
          fontSize: 10.5,
          color: "var(--ink-3)",
          letterSpacing: "0.12em",
          textTransform: "uppercase",
        }}
      >
        Dilanjutkan
      </span>
      <span style={{ fontSize: 13, color: "var(--ink-2)", flex: 1, minWidth: 200 }}>
        Percakapan {turnCount} giliran dari sesi sebelumnya — ajukan pertanyaan lanjutan di bawah atau mulai baru.
      </span>
      <div style={{ display: "flex", gap: 6 }}>
        <button
          type="button"
          onClick={onReset}
          disabled={disabled}
          className="mono"
          style={{
            fontSize: 10.5,
            color: "var(--ink-2)",
            letterSpacing: "0.08em",
            textTransform: "uppercase",
            border: "1px solid var(--rule)",
            background: "var(--paper)",
            padding: "4px 9px",
            borderRadius: 2,
            cursor: disabled ? "not-allowed" : "pointer",
            opacity: disabled ? 0.5 : 1,
          }}
        >
          Mulai baru
        </button>
        <button
          type="button"
          onClick={onDismiss}
          aria-label="Tutup"
          className="mono"
          style={{
            fontSize: 14,
            color: "var(--ink-3)",
            border: "1px solid var(--rule)",
            background: "var(--paper)",
            padding: "2px 9px",
            borderRadius: 2,
            cursor: "pointer",
            lineHeight: 1,
          }}
        >
          ×
        </button>
      </div>
    </div>
  );
}

/** Compact "Q{n}" chip + query text — rendered above every turn's answer
 *  so the conversation reads top-to-bottom like a transcript. */
function TurnQueryLine({
  text,
  index,
  pending = false,
}: {
  text: string;
  index: number;
  pending?: boolean;
}) {
  return (
    <div
      style={{
        display: "flex",
        alignItems: "flex-start",
        gap: 12,
        padding: "10px 14px",
        background: "var(--paper-2)",
        border: "1px solid var(--rule)",
        borderLeft: "2px solid var(--navy, #1a2550)",
        borderRadius: 2,
      }}
    >
      <span
        className="mono"
        style={{
          fontSize: 10.5,
          color: "var(--ink-3)",
          letterSpacing: "0.12em",
          textTransform: "uppercase",
          paddingTop: 2,
          minWidth: 32,
        }}
      >
        Q{index + 1}
      </span>
      <p
        style={{
          margin: 0,
          fontSize: 14.5,
          lineHeight: 1.55,
          color: "var(--ink)",
          flex: 1,
          fontFamily: "var(--font-body-stack)",
        }}
      >
        {text}
        {pending && (
          <span
            className="mono"
            style={{ marginLeft: 8, fontSize: 10.5, color: "var(--ink-3)" }}
          >
            · memproses…
          </span>
        )}
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
