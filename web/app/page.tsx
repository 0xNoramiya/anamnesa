"use client";

import { useCallback, useState } from "react";
import { Masthead } from "@/components/Masthead";
import { QueryInput } from "@/components/QueryInput";
import { AnswerPanel } from "@/components/AnswerPanel";
import { TraceSidebar } from "@/components/TraceSidebar";
import { PdfViewer } from "@/components/PdfViewer";
import { FastSearch } from "@/components/FastSearch";
import { useQueryStream } from "@/lib/useQueryStream";

type Mode = "fast" | "agentic";
interface PdfOpen { docId: string; page: number }

export default function HomePage() {
  const stream = useQueryStream();
  const [mode, setMode] = useState<Mode>("fast");
  const [pdf, setPdf] = useState<PdfOpen | null>(null);
  const openPdf = useCallback(
    (docId: string, page: number) => setPdf({ docId, page }),
    [],
  );
  const closePdf = useCallback(() => setPdf(null), []);

  // Escalate from Fast → Agentic with the current query pre-filled.
  const escalate = useCallback((q: string) => {
    setMode("agentic");
    // Defer one tick so the agentic UI mounts + takes the submit call.
    setTimeout(() => stream.submit(q), 0);
  }, [stream]);

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
              <QueryInput onSubmit={stream.submit} status={stream.status} />

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
                <ThinkingIndicator eventsCount={stream.events.length} />
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

function ThinkingIndicator({ eventsCount }: { eventsCount: number }) {
  return (
    <div className="mt-10 animate-fade-in-up">
      <div className="flex items-center gap-3 mb-3">
        <span className="chapter-mark text-civic">Memproses</span>
        <span className="flex-1 h-px bg-paper-edge" />
      </div>
      <div className="bg-civic/5 border border-civic/20 rounded-lg p-4">
        <p className="text-body-lg text-ink font-medium">
          Agen sedang bekerja
          <span className="ml-2 inline-flex gap-1 align-middle">
            <span className="w-1.5 h-1.5 rounded-full bg-civic animate-pulse" />
            <span className="w-1.5 h-1.5 rounded-full bg-civic animate-pulse [animation-delay:150ms]" />
            <span className="w-1.5 h-1.5 rounded-full bg-civic animate-pulse [animation-delay:300ms]" />
          </span>
        </p>
        <p className="mt-1 text-body text-ink-mid">
          {eventsCount > 0
            ? `${eventsCount} peristiwa tercatat sejauh ini.`
            : "Menunggu langkah pertama."}
        </p>
        <p className="mt-3 text-caption text-ink-faint max-w-[58ch]">
          Opus 4.7 (mode xhigh effort) biasanya memerlukan 2–4 menit untuk
          kueri klinis yang kompleks. Jejak agen di sebelah kanan
          menampilkan setiap keputusan saat terjadi.
        </p>
      </div>
    </div>
  );
}
