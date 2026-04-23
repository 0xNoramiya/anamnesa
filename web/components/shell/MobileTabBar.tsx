"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { NAV_ITEMS } from "./Sidebar";
import { NavIcon } from "./NavIcon";

/**
 * Bottom tab bar for phones. Shows the 5 most-used sections; Agent Track
 * stays hidden on mobile (power-user surface, accessed via the in-view
 * trace rail on Chat).
 */
export function MobileTabBar() {
  const pathname = usePathname();
  const tabs = NAV_ITEMS.slice(0, 5);
  // `position: fixed` locks the bar to the viewport bottom regardless of
  // content height — crucial on mobile where long answer threads used
  // to push a sticky bar off-screen and let the page scroll past it.
  // Main content gets a matching bottom padding via .shell-main-inner so
  // the last-line content isn't hidden behind the bar.
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
      {tabs.map((t) => {
        const active = pathname === t.href || pathname.startsWith(t.href + "/");
        return (
          <Link
            key={t.id}
            href={t.href}
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
            <NavIcon name={t.icon} size={19} />
            <span>{t.label}</span>
          </Link>
        );
      })}
    </nav>
  );
}
