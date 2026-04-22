/**
 * Anamnesa logo — civic A monogram + red cross + teal knowledge-graph nodes.
 * Inline SVG so the glyph inherits `color` via the CSS variables that the
 * theme provider swaps on `html.dark`.
 */
export function LogoMark({ size = 28 }: { size?: number }) {
  return (
    <svg
      width={size}
      height={size}
      viewBox="0 0 32 32"
      fill="none"
      style={{ display: "block" }}
      aria-hidden="true"
    >
      {/* A */}
      <path
        d="M6 28 L14 4 L18 4 L26 28 L22 28 L20.2 22.5 L11.8 22.5 L10 28 Z M13 19 L19 19 L16 10 Z"
        fill="var(--navy)"
      />
      {/* Red cross */}
      <rect x="13" y="12" width="6" height="2" fill="var(--oxblood)" />
      <rect x="15" y="10" width="2" height="6" fill="var(--oxblood)" />
      {/* Knowledge-graph nodes */}
      <circle cx="5" cy="8" r="1.4" fill="var(--teal)" />
      <circle cx="3" cy="13" r="1" fill="var(--teal)" />
      <line x1="5" y1="8" x2="3" y2="13" stroke="var(--teal)" strokeWidth="0.6" />
    </svg>
  );
}

export function Wordmark({ size = 18 }: { size?: number }) {
  return (
    <div style={{ display: "flex", alignItems: "center", gap: 10 }}>
      <LogoMark size={size + 8} />
      <span
        className="display"
        style={{
          fontSize: size,
          fontWeight: 600,
          color: "var(--ink)",
          letterSpacing: "-0.01em",
          fontVariationSettings: "'opsz' 24",
        }}
      >
        Anamnesa
      </span>
    </div>
  );
}
