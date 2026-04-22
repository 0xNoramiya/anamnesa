import type { ReactNode } from "react";
import { Sidebar } from "@/components/shell/Sidebar";
import { MobileTabBar } from "@/components/shell/MobileTabBar";
import "./app-shell.css";

/**
 * Desktop: persistent left sidebar (236 px) + main column.
 * Mobile:  main column full-width + sticky bottom tab bar.
 *
 * The sidebar is hidden on < 768 px via CSS (`.shell-sidebar` class).
 * The mobile tab bar is hidden on >= 768 px.
 */
export default function AppLayout({ children }: { children: ReactNode }) {
  return (
    <div className="shell-root">
      <div className="shell-sidebar">
        <Sidebar />
      </div>
      <main className="shell-main">
        <div className="shell-main-inner">{children}</div>
        <div className="shell-mobile-tabs">
          <MobileTabBar />
        </div>
      </main>
    </div>
  );
}
