"use client";

import { Masthead } from "@/components/Masthead";
import { QueryInput } from "@/components/QueryInput";
import { AnswerPanel } from "@/components/AnswerPanel";
import { TraceSidebar } from "@/components/TraceSidebar";
import { useQueryStream } from "@/lib/useQueryStream";

export default function HomePage() {
  const stream = useQueryStream();

  return (
    <main className="min-h-screen">
      <div className="mx-auto max-w-[1440px] px-8 lg:px-12">
        <Masthead />
        <div className="grid grid-cols-12 gap-10 pt-8 pb-16">
          {/* Main column — query + answer */}
          <section className="col-span-12 lg:col-span-8 xl:col-span-8">
            <QueryInput onSubmit={stream.submit} status={stream.status} />

            {stream.status === "error" && stream.error && (
              <div className="mt-8 border-l-4 border-oxblood pl-5 py-3 text-body text-oxblood-deep">
                <div className="chapter-mark mb-1">Error</div>
                <pre className="font-mono text-caption whitespace-pre-wrap">
                  {stream.error}
                </pre>
              </div>
            )}

            {stream.final && (
              <div className="mt-14">
                <AnswerPanel final={stream.final} />
              </div>
            )}

            {stream.status === "streaming" && !stream.final && (
              <ThinkingIndicator eventsCount={stream.events.length} />
            )}
          </section>

          {/* Sidebar — agent trace */}
          <section className="col-span-12 lg:col-span-4 xl:col-span-4
                              lg:sticky lg:top-8 lg:self-start
                              lg:max-h-[calc(100vh-3rem)]
                              border-l border-paper-edge lg:pl-6
                              pt-4 lg:pt-0">
            <TraceSidebar events={stream.events} status={stream.status} />
          </section>
        </div>
      </div>
    </main>
  );
}

function ThinkingIndicator({ eventsCount }: { eventsCount: number }) {
  return (
    <div className="mt-14 animate-fade-in-up">
      <div className="flex items-center gap-3 mb-3">
        <span className="chapter-mark text-amber">Memproses</span>
        <span className="flex-1 rule origin-left animate-draw-rule" />
      </div>
      <p className="text-body-lg text-ink-mid italic">
        Agen sedang bekerja. {eventsCount > 0 ? `${eventsCount} peristiwa tercatat sejauh ini.` : "Menunggu langkah pertama."}
        <span className="ml-2 inline-flex gap-1 align-middle">
          <span className="w-1 h-1 rounded-full bg-amber animate-pulse" />
          <span className="w-1 h-1 rounded-full bg-amber animate-pulse [animation-delay:150ms]" />
          <span className="w-1 h-1 rounded-full bg-amber animate-pulse [animation-delay:300ms]" />
        </span>
      </p>
      <p className="mt-2 text-caption text-ink-faint max-w-[52ch]">
        Opus 4.7 di mode <em>xhigh effort</em> cenderung memerlukan 2–4
        menit untuk kueri klinis yang kompleks. Jejak agen di sebelah
        kanan menampilkan setiap keputusan saat terjadi.
      </p>
    </div>
  );
}
