import type { SVGProps } from "react";

export type NavIconName =
  | "chat"
  | "search"
  | "book"
  | "clock"
  | "star"
  | "trace"
  | "pill"
  | "sun"
  | "moon"
  | "menu"
  | "x"
  | "external";

interface Props extends Omit<SVGProps<SVGSVGElement>, "name"> {
  name: NavIconName;
  size?: number;
}

export function NavIcon({ name, size = 18, ...rest }: Props) {
  const common = {
    width: size,
    height: size,
    viewBox: "0 0 24 24",
    fill: "none",
    stroke: "currentColor",
    strokeWidth: 1.6,
    strokeLinecap: "round" as const,
    strokeLinejoin: "round" as const,
    ...rest,
  };
  switch (name) {
    case "chat":
      return (
        <svg {...common}>
          <path d="M4 5h16v11H9l-5 4V5z" />
          <path d="M8 10h8M8 13h5" />
        </svg>
      );
    case "search":
      return (
        <svg {...common}>
          <circle cx="11" cy="11" r="6" />
          <path d="M20 20l-4.5-4.5" />
        </svg>
      );
    case "book":
      return (
        <svg {...common}>
          <path d="M4 5v14h16V5H12v14" />
          <path d="M4 5h8" />
        </svg>
      );
    case "clock":
      return (
        <svg {...common}>
          <circle cx="12" cy="12" r="8" />
          <path d="M12 8v4l3 2" />
        </svg>
      );
    case "star":
      return (
        <svg {...common}>
          <path d="M12 4l2.5 5.2 5.5.8-4 4 1 5.5L12 17l-5 2.5 1-5.5-4-4 5.5-.8z" />
        </svg>
      );
    case "trace":
      return (
        <svg {...common}>
          <circle cx="5" cy="6" r="2" />
          <circle cx="5" cy="18" r="2" />
          <circle cx="19" cy="12" r="2" />
          <path d="M7 6h6l4 5M7 18h6l4-5" />
        </svg>
      );
    case "pill":
      return (
        <svg {...common}>
          <rect x="3" y="9.5" width="18" height="7" rx="3.5" transform="rotate(-30 12 13)" />
          <path d="M8.6 16.8L16.8 8.6" />
        </svg>
      );
    case "sun":
      return (
        <svg {...common}>
          <circle cx="12" cy="12" r="4" />
          <path d="M12 3v2M12 19v2M3 12h2M19 12h2M5.6 5.6l1.4 1.4M17 17l1.4 1.4M5.6 18.4L7 17M17 7l1.4-1.4" />
        </svg>
      );
    case "moon":
      return (
        <svg {...common}>
          <path d="M20 14A8 8 0 0110 4a8 8 0 1010 10z" />
        </svg>
      );
    case "menu":
      return (
        <svg {...common}>
          <path d="M4 7h16M4 12h16M4 17h16" />
        </svg>
      );
    case "x":
      return (
        <svg {...common}>
          <path d="M6 6l12 12M18 6L6 18" />
        </svg>
      );
    case "external":
      return (
        <svg {...common}>
          <path d="M14 4h6v6M20 4L10 14M19 13v6a1 1 0 01-1 1H5a1 1 0 01-1-1V6a1 1 0 011-1h6" />
        </svg>
      );
    default:
      return null;
  }
}
