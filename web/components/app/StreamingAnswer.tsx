"use client";

import { useMemo } from "react";
import type { TraceEvent } from "@/lib/types";
import { useI18n } from "@/components/shell/LanguageProvider";

interface Props {
  events: TraceEvent[];
}

/**
 * Assembles the Drafter's live text from `drafter.text_delta` trace
 * events and renders it as a typing-cursor block above (or instead of)
 * the ThinkingIndicator. The Drafter now streams prose FIRST and calls
 * submit_decision second (see agents/prompts/drafter.md), so this
 * surface fills in token-by-token from ~2s after retrieval lands.
 *
 * When stream.final arrives, ChatMode replaces this component with the
 * full AnswerPanel — so the streaming view is only visible during the
 * "composing" phase.
 */
export function StreamingAnswer({ events }: Props) {
  const { t } = useI18n();

  const text = useMemo(() => {
    const parts: string[] = [];
    for (const ev of events) {
      if (ev.agent === "drafter" && ev.event_type === "text_delta") {
        const chunk = ev.payload?.text;
        if (typeof chunk === "string") parts.push(chunk);
      }
    }
    return parts.join("");
  }, [events]);

  if (!text) return null;

  return (
    <section
      className="animate-fade-in-up"
      aria-live="polite"
      style={{
        marginTop: 24,
        padding: "18px 20px",
        background: "var(--paper)",
        border: "1px solid var(--rule)",
        borderLeft: "2px solid var(--teal)",
        borderRadius: 2,
      }}
    >
      <div
        style={{
          display: "flex",
          alignItems: "center",
          gap: 8,
          marginBottom: 10,
        }}
      >
        <span
          className="mono"
          style={{
            fontSize: 10.5,
            color: "var(--teal)",
            letterSpacing: "0.14em",
          }}
        >
          ¶ {t("streaming.eyebrow")}
        </span>
        <span style={{ flex: 1, height: 1, background: "var(--rule)" }} />
        <span
          className="mono"
          style={{ fontSize: 10.5, color: "var(--ink-3)" }}
        >
          {text.length} {t("streaming.chars")}
        </span>
      </div>

      <div
        style={{
          fontSize: 15,
          lineHeight: 1.7,
          color: "var(--ink)",
          whiteSpace: "pre-wrap",
          wordWrap: "break-word",
          overflowWrap: "anywhere",
        }}
      >
        {renderInlineMarkers(text)}
        <span className="stream-cursor" aria-hidden="true">
          ▋
        </span>
      </div>
    </section>
  );
}

/**
 * Minimal inline renderer — converts `[[doc:p:slug]]` markers into
 * mono-styled citation chips while streaming. No full Markdown parse
 * (that happens later in AnswerPanel); we just want to avoid showing
 * raw `[[...]]` brackets while the user reads.
 */
function renderInlineMarkers(text: string): React.ReactNode[] {
  const parts: React.ReactNode[] = [];
  const re = /\[\[([^\]]+)\]\]|\*\*([^*]+?)\*\*/g;
  let last = 0;
  let m: RegExpExecArray | null;
  let i = 0;
  while ((m = re.exec(text)) !== null) {
    if (m.index > last) parts.push(text.slice(last, m.index));
    if (m[1] !== undefined) {
      parts.push(
        <span key={`c-${i++}`} className="cite" title={m[1]}>
          ·
        </span>,
      );
    } else if (m[2] !== undefined) {
      parts.push(
        <strong key={`b-${i++}`}>{m[2]}</strong>,
      );
    }
    last = m.index + m[0].length;
  }
  if (last < text.length) parts.push(text.slice(last));
  return parts;
}
