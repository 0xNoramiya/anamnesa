"use client";

import { useEffect, useState } from "react";

const API_BASE = process.env.NEXT_PUBLIC_ANAMNESA_API ?? "";

interface Props {
  docId: string | null;
  page: number;
  onClose: () => void;
}

/**
 * Modal that displays a cached PDF. Desktop renders an inline iframe using
 * the browser's built-in viewer. Mobile (and iOS Safari in particular) can
 * not render PDFs in iframes reliably, so we show an "open in new tab" card
 * that hands off to the OS's native PDF viewer.
 */
export function PdfViewer({ docId, page, onClose }: Props) {
  const [isMobile, setIsMobile] = useState(false);

  useEffect(() => {
    if (!docId) return;
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "Escape") onClose();
    };
    window.addEventListener("keydown", onKey);
    const prev = document.body.style.overflow;
    document.body.style.overflow = "hidden";
    return () => {
      window.removeEventListener("keydown", onKey);
      document.body.style.overflow = prev;
    };
  }, [docId, onClose]);

  // Track viewport so we can swap iframe → link card on narrow screens.
  useEffect(() => {
    if (typeof window === "undefined") return;
    const mq = window.matchMedia("(max-width: 768px)");
    const update = () => setIsMobile(mq.matches);
    update();
    mq.addEventListener("change", update);
    return () => mq.removeEventListener("change", update);
  }, []);

  if (!docId) return null;

  const src = `${API_BASE.replace(/\/$/, "")}/api/pdf/${docId}#page=${page}&toolbar=1&view=FitH`;
  const externalHref = `${API_BASE.replace(/\/$/, "")}/api/pdf/${docId}#page=${page}`;

  return (
    <div
      className="fixed inset-0 z-50 flex items-stretch justify-center
                 bg-ink/60 backdrop-blur-sm animate-fade-in-up"
      role="dialog"
      aria-modal="true"
      aria-label={`Dokumen ${docId}`}
      onClick={(e) => {
        if (e.target === e.currentTarget) onClose();
      }}
    >
      <div className="w-full max-w-[1100px] m-4 flex flex-col bg-white rounded-lg shadow-card overflow-hidden">
        <header className="flex items-center justify-between gap-3 px-4 py-2.5 border-b border-paper-edge bg-paper">
          <div className="flex items-center gap-3 min-w-0">
            <span className="source-pill shrink-0">
              {docId.startsWith("ppk-fktp") ? "PPK FKTP" : "PNPK"}
            </span>
            <span className="font-mono text-[0.82rem] text-ink truncate">
              {docId}
            </span>
            <span className="text-ink-ghost text-sm">·</span>
            <span className="text-ink-mid text-sm shrink-0">hal {page}</span>
          </div>
          <div className="flex items-center gap-2 shrink-0">
            <a
              href={externalHref}
              target="_blank"
              rel="noreferrer"
              className="text-caption font-mono uppercase tracking-editorial
                         text-ink-mid hover:text-civic transition-colors
                         px-2 py-1 rounded-md hover:bg-paper"
              title="Buka di tab baru"
            >
              Tab baru ↗
            </a>
            <button
              onClick={onClose}
              aria-label="Tutup"
              className="w-8 h-8 flex items-center justify-center rounded-md
                         text-ink-mid hover:bg-paper hover:text-ink transition-colors"
            >
              <svg
                width="16"
                height="16"
                viewBox="0 0 16 16"
                fill="none"
                stroke="currentColor"
                strokeWidth="1.5"
                strokeLinecap="round"
              >
                <path d="M3 3 L13 13 M13 3 L3 13" />
              </svg>
            </button>
          </div>
        </header>
        <div className="flex-1 bg-paper-deep">
          {isMobile ? (
            <div className="h-full flex items-center justify-center p-6">
              <a
                href={externalHref}
                target="_blank"
                rel="noreferrer"
                onClick={onClose}
                className="group w-full max-w-sm bg-white border border-paper-edge
                           rounded-lg p-6 shadow-card hover:border-civic
                           hover:shadow-md transition-all active:scale-[0.98]"
              >
                <div className="flex items-start gap-4">
                  <div
                    className="shrink-0 w-12 h-12 rounded-md bg-civic/10
                               flex items-center justify-center text-civic"
                  >
                    <svg
                      width="22"
                      height="22"
                      viewBox="0 0 24 24"
                      fill="none"
                      stroke="currentColor"
                      strokeWidth="1.7"
                      strokeLinecap="round"
                      strokeLinejoin="round"
                    >
                      <path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z" />
                      <path d="M14 2v6h6" />
                    </svg>
                  </div>
                  <div className="min-w-0 flex-1">
                    <p className="text-caption font-mono uppercase tracking-editorial text-ink-mid">
                      Dokumen · hal {page}
                    </p>
                    <p className="mt-1 text-base font-medium text-ink break-words leading-snug">
                      {docId}
                    </p>
                    <p className="mt-3 text-sm text-civic font-medium inline-flex items-center gap-1.5 group-hover:gap-2 transition-all">
                      Buka PDF di tab baru
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
                        <path d="M7 17L17 7M9 7h8v8" />
                      </svg>
                    </p>
                    <p className="mt-3 text-xs text-ink-mid leading-relaxed">
                      Tampilan PDF bawaan peramban ponsel lebih stabil
                      daripada di dalam aplikasi.
                    </p>
                  </div>
                </div>
              </a>
            </div>
          ) : (
            <iframe
              key={src}
              src={src}
              title={`${docId} hal ${page}`}
              className="w-full h-full border-0"
            />
          )}
        </div>
      </div>
    </div>
  );
}
