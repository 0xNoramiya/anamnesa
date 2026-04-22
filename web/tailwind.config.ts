import type { Config } from "tailwindcss";

/*
 * Anamnesa theme — "Kepmenkes-annotated-edition".
 *
 * Not a generic SaaS palette. Warm paper cream, deep ink, oxblood accent
 * for aging/superseded warnings, muted sage for "current" flags.
 * Inspired by official Indonesian government documents but set in a
 * contemporary editorial type system.
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
        // Paper and ink
        paper: {
          DEFAULT: "#FAF6EB", // warm cream
          deep: "#F1EBD9",    // slight shadow on cream
          edge: "#E7DFCA",    // rule lines, dividers
        },
        ink: {
          DEFAULT: "#1A1914", // warm black — never pure #000
          mid: "#3F3B33",
          faint: "#6E6857",
          ghost: "#9A937F",
        },
        // Accents — pulled from official Indonesian palette
        oxblood: {
          DEFAULT: "#8B2332",
          deep: "#6B1820",
        },
        sage: {
          DEFAULT: "#2E4B3A",
          light: "#90A68F",
        },
        indigo: {
          DEFAULT: "#2B3A52", // editorial blue, not web blue
        },
        amber: {
          DEFAULT: "#B77520", // for warnings / aging
        },
      },
      fontFamily: {
        display: ['"Fraunces"', "Georgia", "serif"],
        body: ['"IBM Plex Sans"', "system-ui", "sans-serif"],
        mono: ['"IBM Plex Mono"', "ui-monospace", "monospace"],
      },
      fontSize: {
        // Editorial scale — bigger display, tighter body
        "display-xl": ["clamp(3rem, 8vw, 6rem)", { lineHeight: "0.95", letterSpacing: "-0.03em" }],
        "display-lg": ["clamp(2rem, 5vw, 3.5rem)", { lineHeight: "1.02", letterSpacing: "-0.025em" }],
        "display-md": ["clamp(1.5rem, 3vw, 2.25rem)", { lineHeight: "1.1", letterSpacing: "-0.02em" }],
        "body-lg": ["1.0625rem", { lineHeight: "1.65" }],
        "body": ["0.95rem", { lineHeight: "1.6" }],
        "caption": ["0.78rem", { lineHeight: "1.45", letterSpacing: "0.02em" }],
      },
      letterSpacing: {
        "editorial": "0.14em",
      },
      boxShadow: {
        "paper": "0 1px 0 0 #E7DFCA, 0 0 0 1px #F1EBD9",
        "sink": "inset 0 1px 2px rgba(26,25,20,0.06)",
      },
      backgroundImage: {
        // Subtle paper grain — SVG data URL, pure CSS, no assets
        "grain": "url(\"data:image/svg+xml;utf8,<svg xmlns='http://www.w3.org/2000/svg' width='160' height='160'><filter id='n'><feTurbulence type='fractalNoise' baseFrequency='0.9' numOctaves='2' stitchTiles='stitch'/><feColorMatrix values='0 0 0 0 0.05  0 0 0 0 0.05  0 0 0 0 0.04  0 0 0 0.035 0'/></filter><rect width='100%25' height='100%25' filter='url(%23n)'/></svg>\")",
      },
      animation: {
        "fade-in-up": "fadeInUp 0.5s cubic-bezier(0.2, 0.8, 0.2, 1) both",
        "draw-rule": "drawRule 0.6s cubic-bezier(0.2, 0.8, 0.2, 1) both",
      },
      keyframes: {
        fadeInUp: {
          "0%": { opacity: "0", transform: "translateY(6px)" },
          "100%": { opacity: "1", transform: "translateY(0)" },
        },
        drawRule: {
          "0%": { transform: "scaleX(0)" },
          "100%": { transform: "scaleX(1)" },
        },
      },
    },
  },
  plugins: [],
};

export default config;
