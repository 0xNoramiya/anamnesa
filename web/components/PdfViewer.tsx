"use client";

import { useEffect } from "react";

const API_BASE = process.env.NEXT_PUBLIC_ANAMNESA_API ?? "";

interface Props {
  docId: string | null;
  page: number;
  onClose: () => void;
}

/**
 * Modal that displays a cached PDF via the browser's built-in viewer
 * (inside an iframe). The backend serves `Content-Disposition: inline`
 * so the iframe renders rather than prompting a download.
 *
 * We append `#page=N&toolbar=1&view=FitH` to the PDF URL — the major
 * browsers honor these fragment params.
 */
export function PdfViewer({ docId, page, onClose }: Props) {
  // Close on Escape.
  useEffect(() => {
    if (!docId) return;
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "Escape") onClose();
    };
    window.addEventListener("keydown", onKey);
    // Lock body scroll while modal is open.
    const prev = document.body.style.overflow;
    document.body.style.overflow = "hidden";
    return () => {
      window.removeEventListener("keydown", onKey);
      document.body.style.overflow = prev;
    };
  }, [docId, onClose]);

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
          <iframe
            key={src}
            src={src}
            title={`${docId} hal ${page}`}
            className="w-full h-full border-0"
          />
        </div>
      </div>
    </div>
  );
}
