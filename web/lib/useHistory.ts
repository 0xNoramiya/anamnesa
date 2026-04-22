"use client";

import { useCallback, useEffect, useState } from "react";
import type { FinalResponse } from "./types";

const STORAGE_KEY = "anamnesa.history.v1";
const MAX_ENTRIES = 20;

export interface HistoryEntry {
  id: string;
  query: string;
  timestamp: number;            // epoch ms
  final: FinalResponse;
}

/**
 * Client-side query history. Persists the last 20 query/answer pairs in
 * localStorage so users can revisit earlier answers without a refresh
 * wiping them. No backend involvement — restoring an entry rebuilds the
 * UI from the stored FinalResponse; it does NOT re-run the pipeline or
 * hit the answer cache (which is a separate, server-side layer).
 */
export function useHistory() {
  const [entries, setEntries] = useState<HistoryEntry[]>([]);
  // Hydrate from localStorage on mount. Kept in a useEffect (not useState
  // initializer) because Next.js SSR runs this file on the server where
  // `localStorage` is undefined — accessing it synchronously during
  // render would crash the build.
  useEffect(() => {
    try {
      const raw = window.localStorage.getItem(STORAGE_KEY);
      if (!raw) return;
      const parsed = JSON.parse(raw) as unknown;
      if (Array.isArray(parsed)) {
        setEntries(parsed as HistoryEntry[]);
      }
    } catch {
      // Corrupted storage — start fresh rather than crash.
    }
  }, []);

  const persist = useCallback((next: HistoryEntry[]) => {
    setEntries(next);
    try {
      window.localStorage.setItem(STORAGE_KEY, JSON.stringify(next));
    } catch {
      // Storage quota exceeded, private mode, etc. — soft-fail.
    }
  }, []);

  const addEntry = useCallback(
    (query: string, final: FinalResponse) => {
      // Dedup: if the same query already tops the list (within 30s),
      // replace rather than duplicate. Prevents double-entries when a
      // user re-submits to watch the agent trace again.
      const now = Date.now();
      const entry: HistoryEntry = {
        id: `${now}-${Math.random().toString(36).slice(2, 8)}`,
        query,
        timestamp: now,
        final,
      };
      setEntries((prev) => {
        const head = prev[0];
        const dedupe =
          head && head.query === query && now - head.timestamp < 30_000;
        const next = dedupe ? [entry, ...prev.slice(1)] : [entry, ...prev];
        const trimmed = next.slice(0, MAX_ENTRIES);
        try {
          window.localStorage.setItem(STORAGE_KEY, JSON.stringify(trimmed));
        } catch {
          // soft-fail
        }
        return trimmed;
      });
    },
    [],
  );

  const clearAll = useCallback(() => {
    persist([]);
  }, [persist]);

  const removeEntry = useCallback(
    (id: string) => {
      const next = entries.filter((e) => e.id !== id);
      persist(next);
    },
    [entries, persist],
  );

  return { entries, addEntry, clearAll, removeEntry };
}
