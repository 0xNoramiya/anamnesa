"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import type {
  FinalResponse,
  QueryCreated,
  StreamEnvelope,
  TraceEvent,
} from "./types";

/** Submit state machine: the lifecycle of one query. */
export type StreamStatus = "idle" | "submitting" | "streaming" | "done" | "error";

/**
 * Backend base URL. Browser talks to FastAPI directly (CORS-enabled) to
 * avoid Next's dev-server rewrite proxy — that proxy buffers and hangs
 * up on long-lived SSE connections. Override per-env via the public env
 * var; empty string (default) = same-origin (for production behind Caddy).
 */
const API_BASE = process.env.NEXT_PUBLIC_ANAMNESA_API ?? "";

function apiUrl(path: string): string {
  return API_BASE ? `${API_BASE.replace(/\/$/, "")}${path}` : path;
}

/** Prior turn passed on a follow-up query so the Normalizer can
 *  condense a terse reply ("dan kalau anak?") into a standalone query. */
export interface PriorTurn {
  query: string;
  answer: string;
}

interface UseQueryStreamState {
  status: StreamStatus;
  queryId: string | null;
  events: TraceEvent[];
  final: FinalResponse | null;
  error: string | null;
  submit: (query: string, priorTurn?: PriorTurn | null) => Promise<void>;
  reset: () => void;
  /** Restore a previous answer from client-side history without re-running. */
  loadFromHistory: (final: FinalResponse) => void;
}

/**
 * Drives one query through POST /api/query → GET /api/stream/{id}.
 *
 * Events arrive as named SSE events (event: trace|final|error|done).
 * We don't use EventSource because our payloads can be large and we want
 * explicit error handling; we hand-roll the reader on fetch + stream.
 */
export function useQueryStream(): UseQueryStreamState {
  const [status, setStatus] = useState<StreamStatus>("idle");
  const [queryId, setQueryId] = useState<string | null>(null);
  const [events, setEvents] = useState<TraceEvent[]>([]);
  const [final, setFinal] = useState<FinalResponse | null>(null);
  const [error, setError] = useState<string | null>(null);
  const abortRef = useRef<AbortController | null>(null);

  useEffect(() => () => abortRef.current?.abort(), []);

  const reset = useCallback(() => {
    abortRef.current?.abort();
    abortRef.current = null;
    setStatus("idle");
    setQueryId(null);
    setEvents([]);
    setFinal(null);
    setError(null);
  }, []);

  const submit = useCallback(async (query: string, priorTurn?: PriorTurn | null) => {
    reset();
    setStatus("submitting");
    const ac = new AbortController();
    abortRef.current = ac;

    try {
      const body: { query: string; prior_query?: string; prior_answer?: string } = {
        query,
      };
      if (priorTurn && priorTurn.query && priorTurn.answer) {
        body.prior_query = priorTurn.query;
        body.prior_answer = priorTurn.answer;
      }
      const createRes = await fetch(apiUrl("/api/query"), {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(body),
        signal: ac.signal,
      });
      if (!createRes.ok) {
        const text = await createRes.text().catch(() => "");
        throw new Error(`POST /api/query ${createRes.status}: ${text}`);
      }
      const created = (await createRes.json()) as QueryCreated;
      setQueryId(created.query_id);

      setStatus("streaming");

      const streamRes = await fetch(apiUrl(created.stream_url), {
        method: "GET",
        headers: { Accept: "text/event-stream" },
        signal: ac.signal,
      });
      if (!streamRes.ok || !streamRes.body) {
        throw new Error(`GET ${created.stream_url} ${streamRes.status}`);
      }

      const reader = streamRes.body
        .pipeThrough(new TextDecoderStream())
        .getReader();
      let buffer = "";
      for (;;) {
        const { value, done } = await reader.read();
        if (done) break;
        buffer += value;
        // Split on SSE message boundary (blank line).
        const parts = buffer.split(/\r?\n\r?\n/);
        buffer = parts.pop() ?? "";
        for (const part of parts) {
          const parsed = parseSseMessage(part);
          if (!parsed) continue;
          handleEnvelope(parsed);
        }
      }
      // Any trailing buffered message.
      if (buffer.trim()) {
        const parsed = parseSseMessage(buffer);
        if (parsed) handleEnvelope(parsed);
      }
      setStatus((prev) => (prev === "error" ? "error" : "done"));
    } catch (err) {
      if ((err as Error).name === "AbortError") return;
      console.error(err);
      setError((err as Error).message ?? String(err));
      setStatus("error");
    }
  }, [reset]);

  function handleEnvelope(env: StreamEnvelope | { kind: "done" }) {
    switch (env.kind) {
      case "trace":
        setEvents((prev) => [...prev, env.payload]);
        return;
      case "final":
        setFinal(env.payload);
        return;
      case "error":
        setError(env.payload.error);
        setStatus("error");
        return;
      case "done":
        return;
    }
  }

  const loadFromHistory = useCallback((restored: FinalResponse) => {
    // Cancel any in-flight stream so we don't overwrite the restored view.
    abortRef.current?.abort();
    abortRef.current = null;
    setEvents([]);
    setError(null);
    setQueryId(restored.query_id);
    setFinal(restored);
    setStatus("done");
  }, []);

  return { status, queryId, events, final, error, submit, reset, loadFromHistory };
}

/** Parse one SSE message block ("event: X\ndata: Y"). */
function parseSseMessage(
  block: string,
): StreamEnvelope | { kind: "done" } | null {
  let eventName = "message";
  const dataLines: string[] = [];
  for (const line of block.split(/\r?\n/)) {
    if (!line || line.startsWith(":")) continue;
    if (line.startsWith("event:")) eventName = line.slice(6).trim();
    else if (line.startsWith("data:")) dataLines.push(line.slice(5).trim());
  }
  const raw = dataLines.join("\n");
  if (eventName === "done") return { kind: "done" };
  if (!raw) return null;
  try {
    const payload = JSON.parse(raw);
    if (eventName === "trace") return { kind: "trace", payload };
    if (eventName === "final") return { kind: "final", payload };
    if (eventName === "error") return { kind: "error", payload };
  } catch {
    return null;
  }
  return null;
}
