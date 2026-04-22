"use client";

import { useEffect, useState } from "react";
import type { FinalResponse } from "@/lib/types";

const API_BASE = process.env.NEXT_PUBLIC_ANAMNESA_API ?? "";
const STORAGE_KEY = "anamnesa.feedback.v1";

interface Props {
  final: FinalResponse;
  queryText?: string;
}

type Rating = "up" | "down";

interface LocalMemo {
  rating: Rating;
  at: number;
  note?: string;
}

function readMemo(queryId: string): LocalMemo | null {
  try {
    const raw = window.localStorage.getItem(STORAGE_KEY);
    if (!raw) return null;
    const map = JSON.parse(raw) as Record<string, LocalMemo>;
    return map[queryId] ?? null;
  } catch {
    return null;
  }
}

function writeMemo(queryId: string, memo: LocalMemo) {
  try {
    const raw = window.localStorage.getItem(STORAGE_KEY);
    const map = raw ? (JSON.parse(raw) as Record<string, LocalMemo>) : {};
    map[queryId] = memo;
    // Keep the map small — at ~250 bytes/entry, cap at 200 entries.
    const keys = Object.keys(map);
    if (keys.length > 200) {
      const sorted = keys.sort((a, b) => (map[a].at - map[b].at));
      for (const k of sorted.slice(0, keys.length - 200)) delete map[k];
    }
    window.localStorage.setItem(STORAGE_KEY, JSON.stringify(map));
  } catch {
    // soft-fail
  }
}

export function FeedbackBar({ final, queryText }: Props) {
  const [rating, setRating] = useState<Rating | null>(null);
  const [note, setNote] = useState("");
  const [noteOpen, setNoteOpen] = useState(false);
  const [savingNote, setSavingNote] = useState(false);
  const [noteSaved, setNoteSaved] = useState(false);
  const [failed, setFailed] = useState<string | null>(null);

  // Rehydrate prior vote from localStorage so refresh doesn't
  // "reset" an expressed opinion.
  useEffect(() => {
    const memo = readMemo(final.query_id);
    if (memo) {
      setRating(memo.rating);
      if (memo.note) setNote(memo.note);
    } else {
      setRating(null);
      setNote("");
    }
    setNoteOpen(false);
    setNoteSaved(false);
    setFailed(null);
  }, [final.query_id]);

  const submit = async (nextRating: Rating, nextNote?: string) => {
    setFailed(null);
    try {
      const r = await fetch(`${API_BASE.replace(/\/$/, "")}/api/feedback`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          query_id: final.query_id,
          query_text: queryText ?? "",
          rating: nextRating,
          note: nextNote ?? undefined,
        }),
      });
      if (!r.ok) {
        const txt = await r.text().catch(() => "");
        throw new Error(`${r.status}: ${txt}`);
      }
      writeMemo(final.query_id, {
        rating: nextRating,
        at: Date.now(),
        note: nextNote,
      });
      setRating(nextRating);
    } catch (err) {
      setFailed((err as Error).message || "gagal kirim");
    }
  };

  const handleThumb = async (r: Rating) => {
    // Optimistic toggle: if the user re-taps the same thumb, treat as a
    // second vote (we don't have undo), but still submit so the
    // intention is recorded.
    await submit(r);
    if (r === "down") setNoteOpen(true);
  };

  const handleNoteSave = async () => {
    if (!rating) return;
    setSavingNote(true);
    await submit(rating, note.trim() || undefined);
    setSavingNote(false);
    setNoteSaved(true);
    setTimeout(() => setNoteSaved(false), 1800);
  };

  return (
    <div className="mt-8 pt-5 border-t border-paper-edge">
      <div className="flex items-center gap-3 flex-wrap">
        <span className="text-caption font-mono uppercase tracking-editorial text-ink-faint">
          Apakah jawaban ini membantu?
        </span>
        <div className="flex items-center gap-1">
          <ThumbButton
            active={rating === "up"}
            onClick={() => handleThumb("up")}
            direction="up"
            label="Ya, membantu"
          />
          <ThumbButton
            active={rating === "down"}
            onClick={() => handleThumb("down")}
            direction="down"
            label="Kurang membantu"
          />
        </div>
        {rating && (
          <span className="text-caption text-ink-faint">
            {rating === "up" ? "Terima kasih." : "Kami akan memeriksa kutipan."}
          </span>
        )}
        {failed && (
          <span className="text-caption text-oxblood">
            (gagal simpan: {failed})
          </span>
        )}
      </div>

      {noteOpen && rating === "down" && (
        <div className="mt-3 animate-fade-in-up">
          <label className="block text-caption text-ink-mid mb-1">
            Apa yang kurang? (opsional — untuk perbaikan korpus / prompt)
          </label>
          <textarea
            value={note}
            onChange={(e) => setNote(e.target.value)}
            rows={2}
            maxLength={2000}
            placeholder="Contoh: dosis pediatrik tidak tersedia; pedoman yang dikutip sudah usang…"
            className="w-full bg-white border border-paper-edge rounded-md
                       px-3 py-2 text-body leading-relaxed
                       focus:outline-none focus:border-civic/60
                       focus:shadow-card transition-shadow resize-y"
          />
          <div className="mt-2 flex items-center gap-2">
            <button
              type="button"
              onClick={handleNoteSave}
              disabled={savingNote}
              className="px-3 py-1 rounded-md bg-civic text-white text-caption
                         font-medium disabled:opacity-40 enabled:hover:bg-civic-hover
                         transition-colors"
            >
              {savingNote ? "Menyimpan…" : noteSaved ? "Tersimpan ✓" : "Simpan catatan"}
            </button>
            <button
              type="button"
              onClick={() => setNoteOpen(false)}
              className="text-caption font-mono uppercase tracking-editorial
                         text-ink-faint hover:text-ink-mid transition-colors px-2 py-1"
            >
              Tutup
            </button>
          </div>
        </div>
      )}
    </div>
  );
}

function ThumbButton({
  active,
  onClick,
  direction,
  label,
}: {
  active: boolean;
  onClick: () => void;
  direction: "up" | "down";
  label: string;
}) {
  return (
    <button
      type="button"
      onClick={onClick}
      aria-pressed={active}
      aria-label={label}
      title={label}
      className={`w-8 h-8 inline-flex items-center justify-center rounded-md
                  border transition-colors
                  ${active
                    ? direction === "up"
                      ? "bg-civic/10 border-civic/40 text-civic"
                      : "bg-oxblood/10 border-oxblood/40 text-oxblood"
                    : "border-transparent text-ink-ghost hover:bg-paper-deep hover:text-ink-mid"
                  }`}
    >
      {direction === "up" ? (
        <svg width="16" height="16" viewBox="0 0 24 24" fill={active ? "currentColor" : "none"}
             stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round">
          <path d="M7 10v11M20 9h-6l1.4-4.5c.2-1-.5-2-1.5-2-.6 0-1.2.3-1.5.8L7 10" />
        </svg>
      ) : (
        <svg width="16" height="16" viewBox="0 0 24 24" fill={active ? "currentColor" : "none"}
             stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round">
          <path d="M17 14V3M4 15h6l-1.4 4.5c-.2 1 .5 2 1.5 2 .6 0 1.2-.3 1.5-.8L17 14" />
        </svg>
      )}
    </button>
  );
}
