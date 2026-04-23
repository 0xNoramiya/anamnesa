"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { NAV_ITEMS } from "./Sidebar";
import { NavIcon } from "./NavIcon";
import { useI18n } from "./LanguageProvider";

/**
 * Bottom tab bar for phones. Shows the 5 most-used sections; Agent Track
 * stays hidden on mobile (power-user surface, accessed via the in-view
 * trace rail on Chat).
 *
 * `position: fixed` so long answer threads don't push the bar off the
 * viewport. Main content gets a matching bottom padding via
 * .shell-main-inner so the last row isn't hidden behind the bar.
 */
export function MobileTabBar() {
  const pathname = usePathname();
  const { t } = useI18n();
  const tabs = NAV_ITEMS.slice(0, 5);
  return (
    <nav
      style={{
        position: "fixed",
        bottom: 0,
        left: 0,
        right: 0,
        background: "var(--paper-2)",
        borderTop: "1px solid var(--rule)",
        display: "flex",
        paddingBottom: "env(safe-area-inset-bottom)",
        height: "calc(62px + env(safe-area-inset-bottom))",
        zIndex: 40,
      }}
    >
      {tabs.map((tab) => {
        const active = pathname === tab.href || pathname.startsWith(tab.href + "/");
        return (
          <Link
            key={tab.id}
            href={tab.href}
            style={{
              flex: 1,
              display: "flex",
              flexDirection: "column",
              alignItems: "center",
              justifyContent: "center",
              gap: 3,
              background: "transparent",
              border: "none",
              cursor: "pointer",
              color: active ? "var(--navy)" : "var(--ink-3)",
              borderTop: active ? "2px solid var(--navy)" : "2px solid transparent",
              fontSize: 10.5,
              fontFamily: "var(--font-body-stack)",
              fontWeight: active ? 500 : 400,
              paddingTop: 6,
              textDecoration: "none",
            }}
          >
            <NavIcon name={tab.icon} size={19} />
            <span>{t(tab.labelKey)}</span>
          </Link>
        );
      })}
    </nav>
  );
}
