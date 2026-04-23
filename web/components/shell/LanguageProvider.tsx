"use client";

import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useState,
  type ReactNode,
} from "react";
import { LANGS, translate, type Lang } from "@/lib/i18n";

interface LangState {
  lang: Lang;
  t: (key: string) => string;
  setLang: (l: Lang) => void;
  toggle: () => void;
}

const Ctx = createContext<LangState>({
  lang: "id",
  t: (k) => k,
  setLang: () => {},
  toggle: () => {},
});

const STORAGE_KEY = "anamnesa.lang.v1";

export function LanguageProvider({ children }: { children: ReactNode }) {
  const [lang, setLangState] = useState<Lang>("id");

  useEffect(() => {
    try {
      const saved = window.localStorage.getItem(STORAGE_KEY);
      if (saved && LANGS.includes(saved as Lang)) {
        setLangState(saved as Lang);
        return;
      }
      // No preference → take browser hint; default to `id`. We keep the
      // Indonesian-first posture (the product is for Indonesian doctors)
      // but flip to English for users whose browser doesn't set id/in.
      const browserLang = (
        typeof navigator !== "undefined" ? navigator.language : "id"
      )
        .toLowerCase()
        .slice(0, 2);
      setLangState(browserLang === "id" || browserLang === "in" ? "id" : "en");
    } catch {
      // localStorage / navigator blocked — stay on the id default.
    }
  }, []);

  const setLang = useCallback((l: Lang) => {
    setLangState(l);
    try {
      window.localStorage.setItem(STORAGE_KEY, l);
    } catch {
      // soft-fail
    }
  }, []);

  const toggle = useCallback(() => setLang(lang === "id" ? "en" : "id"), [lang, setLang]);

  const value = useMemo<LangState>(
    () => ({
      lang,
      t: (key: string) => translate(lang, key),
      setLang,
      toggle,
    }),
    [lang, setLang, toggle],
  );

  return <Ctx.Provider value={value}>{children}</Ctx.Provider>;
}

export function useI18n() {
  return useContext(Ctx);
}
