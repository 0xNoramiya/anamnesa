import type { ReactNode } from "react";

interface Props {
  title: string;
  subtitle?: string;
  children?: ReactNode;
}

export function TopBar({ title, subtitle, children }: Props) {
  return (
    <header
      style={{
        display: "flex",
        alignItems: "center",
        gap: 16,
        padding: "14px 24px",
        borderBottom: "1px solid var(--rule)",
        background: "var(--paper)",
        flexShrink: 0,
        minHeight: 64,
      }}
    >
      <div style={{ flex: 1, minWidth: 0 }}>
        <h1
          className="display"
          style={{
            margin: 0,
            fontSize: 20,
            fontWeight: 500,
            color: "var(--ink)",
            letterSpacing: "-0.01em",
          }}
        >
          {title}
        </h1>
        {subtitle && (
          <div className="mono" style={{ fontSize: 11, color: "var(--ink-3)", marginTop: 2 }}>
            {subtitle}
          </div>
        )}
      </div>
      {children}
    </header>
  );
}
