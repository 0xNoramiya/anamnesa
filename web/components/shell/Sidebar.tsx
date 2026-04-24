"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { LogoMark, Wordmark } from "./Logo";
import { NavIcon, type NavIconName } from "./NavIcon";
import { useTheme } from "./ThemeProvider";
import { useI18n } from "./LanguageProvider";

interface NavItem {
  id: string;
  labelKey: string;
  subKey: string;
  icon: NavIconName;
  shortcut: string;
  href: string;
}

export const NAV_ITEMS: NavItem[] = [
  { id: "chat",      labelKey: "nav.chat",       subKey: "nav.chat.sub",       icon: "chat",   shortcut: "G C", href: "/chat" },
  { id: "pencarian", labelKey: "nav.search",     subKey: "nav.search.sub",     icon: "search", shortcut: "G P", href: "/pencarian" },
  { id: "obat",      labelKey: "nav.obat",       subKey: "nav.obat.sub",       icon: "pill",   shortcut: "G O", href: "/obat" },
  { id: "guideline", labelKey: "nav.guideline",  subKey: "nav.guideline.sub",  icon: "book",   shortcut: "G G", href: "/guideline" },
  { id: "riwayat",   labelKey: "nav.history",    subKey: "nav.history.sub",    icon: "clock",  shortcut: "G R", href: "/riwayat" },
  { id: "favorit",   labelKey: "nav.favorites",  subKey: "nav.favorites.sub",  icon: "star",   shortcut: "G F", href: "/favorit" },
  { id: "trace",     labelKey: "nav.trace",      subKey: "nav.trace.sub",      icon: "trace",  shortcut: "G T", href: "/agent-track" },
];

interface Props {
  collapsed?: boolean;
}

export function Sidebar({ collapsed = false }: Props) {
  const pathname = usePathname();
  const { dark, toggle } = useTheme();
  const { t, toggle: toggleLang } = useI18n();

  const isActive = (href: string) => pathname === href || pathname.startsWith(href + "/");

  return (
    <aside
      style={{
        width: collapsed ? 64 : 236,
        background: "var(--paper-2)",
        borderRight: "1px solid var(--rule)",
        display: "flex",
        flexDirection: "column",
        flexShrink: 0,
        transition: "width 0.2s",
        height: "100%",
      }}
    >
      <div
        style={{
          padding: collapsed ? "18px 18px 14px" : "18px 20px 14px",
          borderBottom: "1px solid var(--rule)",
        }}
      >
        <Link
          href="/"
          aria-label={t("sidebar.home")}
          style={{ textDecoration: "none", color: "inherit" }}
        >
          {collapsed ? <LogoMark size={28} /> : <Wordmark size={17} />}
        </Link>
      </div>

      <nav
        style={{ flex: 1, padding: "14px 10px", overflowY: "auto" }}
        className="scroll-civic"
      >
        {!collapsed && (
          <div className="label" style={{ padding: "0 10px 8px" }}>
            {t("nav.navigation")}
          </div>
        )}
        {NAV_ITEMS.map((item) => {
          const active = isActive(item.href);
          const label = t(item.labelKey);
          const sub = t(item.subKey);
          return (
            <Link
              key={item.id}
              href={item.href}
              title={collapsed ? label : undefined}
              style={{
                display: "flex",
                alignItems: "center",
                gap: 12,
                width: "100%",
                padding: collapsed ? "10px 12px" : "9px 10px",
                background: active ? "var(--paper)" : "transparent",
                border: "1px solid",
                borderColor: active ? "var(--rule)" : "transparent",
                borderLeft: active ? "2px solid var(--navy)" : "1px solid transparent",
                color: active ? "var(--ink)" : "var(--ink-2)",
                fontFamily: "var(--font-body-stack)",
                fontSize: 13.5,
                textAlign: "left",
                cursor: "pointer",
                marginBottom: 2,
                borderRadius: 2,
                justifyContent: collapsed ? "center" : "flex-start",
                fontWeight: active ? 500 : 400,
                textDecoration: "none",
              }}
            >
              <NavIcon name={item.icon} />
              {!collapsed && (
                <div style={{ flex: 1, minWidth: 0 }}>
                  <div>{label}</div>
                  <div className="mono" style={{ fontSize: 10.5, color: "var(--ink-4)", marginTop: 1 }}>
                    {sub}
                  </div>
                </div>
              )}
              {!collapsed && (
                <span className="mono" style={{ fontSize: 10, color: "var(--ink-4)" }}>
                  {item.shortcut}
                </span>
              )}
            </Link>
          );
        })}
      </nav>

      <div
        style={{
          borderTop: "1px solid var(--rule)",
          padding: collapsed ? "10px" : "14px",
        }}
      >
        {!collapsed && (
          <div
            className="mono"
            style={{
              fontSize: 10.5,
              color: "var(--ink-3)",
              lineHeight: 1.5,
              marginBottom: 10,
            }}
          >
            {t("sidebar.corpus_prefix")}{" "}
            <span style={{ color: "var(--ink)" }}>{t("sidebar.docs")}</span> · {" "}
            <span style={{ color: "var(--ink)" }}>{t("sidebar.chunks")}</span>
            <br />
            {t("sidebar.legal")}
          </div>
        )}
        <div style={{ display: "flex", gap: 6 }}>
          <button
            type="button"
            onClick={toggle}
            style={{
              display: "flex",
              alignItems: "center",
              gap: 8,
              flex: 1,
              padding: "7px 10px",
              background: "transparent",
              border: "1px solid var(--rule)",
              borderRadius: 2,
              color: "var(--ink-2)",
              cursor: "pointer",
              fontSize: 12.5,
              fontFamily: "var(--font-body-stack)",
              justifyContent: collapsed ? "center" : "flex-start",
            }}
            aria-label={dark ? t("sidebar.theme_light") : t("sidebar.theme_dark")}
          >
            <NavIcon name={dark ? "sun" : "moon"} size={14} />
            {!collapsed && (
              <span>{dark ? t("sidebar.theme_light") : t("sidebar.theme_dark")}</span>
            )}
          </button>
          <button
            type="button"
            onClick={toggleLang}
            title={t("sidebar.toggle_language")}
            aria-label={t("sidebar.toggle_language")}
            className="mono"
            style={{
              padding: "7px 10px",
              background: "transparent",
              border: "1px solid var(--rule)",
              borderRadius: 2,
              color: "var(--ink-2)",
              cursor: "pointer",
              fontSize: 11,
              letterSpacing: "0.08em",
              textTransform: "uppercase",
              minWidth: collapsed ? 40 : "auto",
            }}
          >
            {t("sidebar.toggle_language").slice(0, 2).toUpperCase() === "EN" ? "EN" : "ID"}
          </button>
        </div>
      </div>
    </aside>
  );
}
