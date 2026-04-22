"use client";

import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useState,
  type ReactNode,
} from "react";

interface ThemeState {
  dark: boolean;
  toggle: () => void;
  setDark: (v: boolean) => void;
}

const ThemeCtx = createContext<ThemeState>({
  dark: false,
  toggle: () => {},
  setDark: () => {},
});

const STORAGE_KEY = "anamnesa.theme.v1";

export function ThemeProvider({ children }: { children: ReactNode }) {
  const [dark, setDarkState] = useState(false);

  // Hydrate from localStorage on mount (SSR-safe).
  useEffect(() => {
    try {
      const saved = window.localStorage.getItem(STORAGE_KEY);
      if (saved === "dark") setDarkState(true);
      else if (saved === "light") setDarkState(false);
      else {
        // No preference → mirror system.
        setDarkState(window.matchMedia("(prefers-color-scheme: dark)").matches);
      }
    } catch {
      // localStorage unavailable — stay light.
    }
  }, []);

  // Reflect on <html> so CSS vars swap palette-wide.
  useEffect(() => {
    document.documentElement.classList.toggle("dark", dark);
  }, [dark]);

  const setDark = useCallback((v: boolean) => {
    setDarkState(v);
    try {
      window.localStorage.setItem(STORAGE_KEY, v ? "dark" : "light");
    } catch {
      // soft-fail
    }
  }, []);

  const toggle = useCallback(() => setDark(!dark), [dark, setDark]);

  return (
    <ThemeCtx.Provider value={{ dark, toggle, setDark }}>
      {children}
    </ThemeCtx.Provider>
  );
}

export function useTheme() {
  return useContext(ThemeCtx);
}
