import type { Config } from "tailwindcss";

/*
 * Anamnesa theme — civic-tech clinical database.
 *
 * Inspired by pasal.id's aesthetic (Indonesian legal document browser):
 * clean off-white, clear slate text, institutional blue for interactive,
 * status badges for regulation currency. Serif display is RESERVED for
 * the "Anamnesa" wordmark only — every other piece of text is sans-serif
 * for readability on a physician's phone during a shift.
 */

const config: Config = {
  content: [
    "./app/**/*.{ts,tsx}",
    "./components/**/*.{ts,tsx}",
    "./lib/**/*.{ts,tsx}",
  ],
  theme: {
    extend: {
      colors: {
        // Backgrounds
        paper: {
          DEFAULT: "#FAFAFA",  // near-white page
          deep: "#F4F4F2",     // panel tint
          edge: "#E5E5E2",     // rule / border
        },
        // Ink — cool slate, government-doc neutral
        ink: {
          DEFAULT: "#0F172A",
          mid: "#334155",
          faint: "#64748B",
          ghost: "#94A3B8",
        },
        // Institutional blue — interactive, links, primary CTA
        civic: {
          DEFAULT: "#1E40AF",
          hover: "#1E3A8A",
          tint: "#DBEAFE",
        },
        // Status (for regulation currency / refusal warnings)
        oxblood: {
          DEFAULT: "#B91C1C",  // refusal / withdrawn
          deep: "#7F1D1D",
          tint: "#FEE2E2",
        },
        amber: {
          DEFAULT: "#B45309",  // aging warning
          deep: "#78350F",
          tint: "#FEF3C7",
        },
        sage: {
          DEFAULT: "#166534",  // current / OK
          tint: "#DCFCE7",
        },
      },
      fontFamily: {
        display: ['"Fraunces"', "Georgia", "serif"],
        body: ['"IBM Plex Sans"', "system-ui", "sans-serif"],
        mono: ['"IBM Plex Mono"', "ui-monospace", "monospace"],
      },
      fontSize: {
        "display-xl": ["clamp(2.5rem, 6vw, 4.25rem)", { lineHeight: "1", letterSpacing: "-0.03em" }],
        "display-lg": ["clamp(1.75rem, 4vw, 2.75rem)", { lineHeight: "1.1", letterSpacing: "-0.025em" }],
        "display-md": ["clamp(1.25rem, 2.5vw, 1.75rem)", { lineHeight: "1.2", letterSpacing: "-0.015em" }],
        "body-lg": ["1rem", { lineHeight: "1.7" }],
        "body": ["0.9375rem", { lineHeight: "1.6" }],
        "caption": ["0.78rem", { lineHeight: "1.4", letterSpacing: "0.01em" }],
      },
      letterSpacing: {
        "editorial": "0.08em",
      },
      borderRadius: {
        "md": "6px",
        "lg": "10px",
      },
      boxShadow: {
        "card": "0 1px 2px rgba(15, 23, 42, 0.04), 0 0 0 1px #E5E5E2",
        "card-hover": "0 2px 8px rgba(15, 23, 42, 0.08), 0 0 0 1px #CBD5E1",
      },
      animation: {
        "fade-in-up": "fadeInUp 0.45s cubic-bezier(0.2, 0.8, 0.2, 1) both",
      },
      keyframes: {
        fadeInUp: {
          "0%": { opacity: "0", transform: "translateY(4px)" },
          "100%": { opacity: "1", transform: "translateY(0)" },
        },
      },
    },
  },
  plugins: [],
};

export default config;
