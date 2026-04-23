"use client";

import { useCallback, useEffect, useState } from "react";
import type { FinalResponse } from "./types";

const STORAGE_KEY = "anamnesa.favorites.v1";

export interface FavoriteAnswer {
  kind: "answer";
  id: string;              // query_id
  query: string;
  final: FinalResponse;
  saved_at: number;
}

export interface FavoriteChunk {
  kind: "chunk";
  id: string;              // citation.key
  doc_id: string;
  page: number;
  section_slug: string;
  chunk_text: string;
  saved_at: number;
}

export interface FavoriteDoc {
  kind: "doc";
  id: string;              // doc_id
  title: string;
  source_type: string;
  year: number;
  currency_status?: string;
  saved_at: number;
}

export type Favorite = FavoriteAnswer | FavoriteChunk | FavoriteDoc;

interface Store {
  answers: Record<string, FavoriteAnswer>;
  chunks: Record<string, FavoriteChunk>;
  docs: Record<string, FavoriteDoc>;
}

const EMPTY_STORE: Store = { answers: {}, chunks: {}, docs: {} };

function readStore(): Store {
  if (typeof window === "undefined") return EMPTY_STORE;
  try {
    const raw = window.localStorage.getItem(STORAGE_KEY);
    if (!raw) return EMPTY_STORE;
    const parsed = JSON.parse(raw);
    return {
      answers: parsed.answers ?? {},
      chunks: parsed.chunks ?? {},
      docs: parsed.docs ?? {},
    };
  } catch {
    return EMPTY_STORE;
  }
}

function writeStore(s: Store) {
  try {
    window.localStorage.setItem(STORAGE_KEY, JSON.stringify(s));
  } catch {
    // soft-fail (quota / private mode)
  }
}

/**
 * Client-side favourites — star/unstar answers, individual citation
 * chunks, or whole guideline documents. Persisted in localStorage so
 * the set survives refresh; no server round-trip.
 */
export function useFavorites() {
  const [store, setStore] = useState<Store>(EMPTY_STORE);

  useEffect(() => {
    setStore(readStore());
  }, []);

  const save = useCallback((next: Store) => {
    setStore(next);
    writeStore(next);
  }, []);

  const isFav = useCallback(
    (kind: Favorite["kind"], id: string): boolean => {
      if (kind === "answer") return !!store.answers[id];
      if (kind === "chunk") return !!store.chunks[id];
      return !!store.docs[id];
    },
    [store],
  );

  const toggleAnswer = useCallback(
    (query: string, final: FinalResponse) => {
      setStore((prev) => {
        const id = final.query_id;
        const next = { ...prev, answers: { ...prev.answers } };
        if (next.answers[id]) {
          delete next.answers[id];
        } else {
          next.answers[id] = {
            kind: "answer",
            id,
            query,
            final,
            saved_at: Date.now(),
          };
        }
        writeStore(next);
        return next;
      });
    },
    [],
  );

  const toggleChunk = useCallback(
    (citation: { key: string; doc_id: string; page: number; section_slug: string; chunk_text: string }) => {
      setStore((prev) => {
        const next = { ...prev, chunks: { ...prev.chunks } };
        if (next.chunks[citation.key]) {
          delete next.chunks[citation.key];
        } else {
          next.chunks[citation.key] = {
            kind: "chunk",
            id: citation.key,
            doc_id: citation.doc_id,
            page: citation.page,
            section_slug: citation.section_slug,
            chunk_text: citation.chunk_text,
            saved_at: Date.now(),
          };
        }
        writeStore(next);
        return next;
      });
    },
    [],
  );

  const toggleDoc = useCallback(
    (doc: { doc_id: string; title: string; source_type: string; year: number; currency_status?: string }) => {
      setStore((prev) => {
        const next = { ...prev, docs: { ...prev.docs } };
        if (next.docs[doc.doc_id]) {
          delete next.docs[doc.doc_id];
        } else {
          next.docs[doc.doc_id] = {
            kind: "doc",
            id: doc.doc_id,
            title: doc.title,
            source_type: doc.source_type,
            year: doc.year,
            currency_status: doc.currency_status,
            saved_at: Date.now(),
          };
        }
        writeStore(next);
        return next;
      });
    },
    [],
  );

  const remove = useCallback((kind: Favorite["kind"], id: string) => {
    setStore((prev) => {
      const next: Store = {
        answers: { ...prev.answers },
        chunks: { ...prev.chunks },
        docs: { ...prev.docs },
      };
      if (kind === "answer") delete next.answers[id];
      else if (kind === "chunk") delete next.chunks[id];
      else delete next.docs[id];
      writeStore(next);
      return next;
    });
  }, []);

  const clearAll = useCallback(() => save(EMPTY_STORE), [save]);

  const answers = Object.values(store.answers).sort((a, b) => b.saved_at - a.saved_at);
  const chunks = Object.values(store.chunks).sort((a, b) => b.saved_at - a.saved_at);
  const docs = Object.values(store.docs).sort((a, b) => b.saved_at - a.saved_at);
  const total = answers.length + chunks.length + docs.length;

  return {
    answers,
    chunks,
    docs,
    total,
    isFav,
    toggleAnswer,
    toggleChunk,
    toggleDoc,
    remove,
    clearAll,
  };
}
