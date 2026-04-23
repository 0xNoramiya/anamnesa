"use client";

import Link from "next/link";
import type { ReactNode } from "react";
import { Wordmark } from "@/components/shell/Logo";
import { useI18n } from "@/components/shell/LanguageProvider";
import { LANG_LABELS, type Lang } from "@/lib/i18n";

/**
 * Thin chrome for the public docs pages (/legal, /mcp, /api) — keeps
 * the landing-page aesthetic (sticky blurred header, navy CTA, quiet
 * footer) without pulling in the app shell sidebar/mobile tabs. Each
 * doc page supplies its own body content via children.
 */
interface DocPageProps {
  title: string;
  eyebrow?: string;
  subtitle?: string;
  children: ReactNode;
}

export function DocPage({ title, eyebrow, subtitle, children }: DocPageProps) {
  const { t } = useI18n();
  return (
    <div style={{ background: "var(--paper)", color: "var(--ink)", minHeight: "100vh" }}>
      <DocHeader />

      <main
        style={{
          padding: "clamp(40px, 7vw, 72px) clamp(20px, 5vw, 56px) 64px",
          maxWidth: 860,
          margin: "0 auto",
        }}
      >
        {eyebrow && (
          <div
            className="mono"
            style={{
              fontSize: 10.5,
              color: "var(--oxblood)",
              letterSpacing: "0.16em",
              textTransform: "uppercase",
              marginBottom: 12,
            }}
          >
            {eyebrow}
          </div>
        )}
        <h1
          className="display"
          style={{
            fontSize: "clamp(30px, 5vw, 48px)",
            lineHeight: 1.1,
            margin: 0,
            fontWeight: 500,
            letterSpacing: "-0.02em",
            color: "var(--ink)",
            fontVariationSettings: "'opsz' 48, 'SOFT' 25",
            maxWidth: 760,
          }}
        >
          {title}
        </h1>
        {subtitle && (
          <p
            style={{
              fontSize: "clamp(15px, 1.8vw, 17px)",
              lineHeight: 1.6,
              marginTop: 14,
              color: "var(--ink-2)",
              maxWidth: 640,
            }}
          >
            {subtitle}
          </p>
        )}

        <div style={{ marginTop: 32 }}>{children}</div>
      </main>

      <DocFooter />
      <BackLink label={t("docs.back")} />
    </div>
  );
}

function DocHeader() {
  const { t, lang, setLang } = useI18n();
  return (
    <div
      style={{
        position: "sticky",
        top: 0,
        zIndex: 10,
        background: "color-mix(in oklch, var(--paper) 92%, transparent)",
        backdropFilter: "blur(8px)",
        WebkitBackdropFilter: "blur(8px)",
        borderBottom: "1px solid var(--rule)",
        padding: "12px clamp(18px, 5vw, 56px)",
        display: "flex",
        alignItems: "center",
        gap: 14,
      }}
    >
      <Link href="/" style={{ textDecoration: "none", color: "inherit" }}>
        <Wordmark size={15} />
      </Link>
      <div style={{ flex: 1 }} />
      <DocNavLink href="/legal" label={t("docs.nav.legal")} />
      <DocNavLink href="/mcp" label={t("docs.nav.mcp")} />
      <DocNavLink href="/api" label={t("docs.nav.api")} />
      <LangSwitch lang={lang} onChange={setLang} />
      <Link
        href="/chat"
        className="btn btn-primary"
        style={{ padding: "8px 14px", fontSize: 13 }}
      >
        {t("landing.cta.open")}
      </Link>
    </div>
  );
}

function DocNavLink({ href, label }: { href: string; label: string }) {
  return (
    <Link
      href={href}
      className="mono doc-navlink"
      style={{
        fontSize: 11,
        color: "var(--ink-2)",
        textDecoration: "none",
        letterSpacing: "0.08em",
        textTransform: "uppercase",
        padding: "4px 8px",
      }}
    >
      {label}
    </Link>
  );
}

function LangSwitch({ lang, onChange }: { lang: Lang; onChange: (l: Lang) => void }) {
  return (
    <div
      role="group"
      aria-label="Language"
      className="mono"
      style={{
        display: "inline-flex",
        border: "1px solid var(--rule)",
        borderRadius: 2,
        overflow: "hidden",
        fontSize: 10.5,
        letterSpacing: "0.08em",
      }}
    >
      {(["id", "en"] as Lang[]).map((l) => {
        const active = lang === l;
        return (
          <button
            key={l}
            type="button"
            onClick={() => onChange(l)}
            aria-pressed={active}
            title={LANG_LABELS[l]}
            style={{
              padding: "5px 9px",
              background: active ? "var(--navy)" : "transparent",
              color: active ? "var(--paper)" : "var(--ink-2)",
              border: "none",
              cursor: "pointer",
              fontFamily: "var(--font-mono-stack)",
              textTransform: "uppercase",
            }}
          >
            {l}
          </button>
        );
      })}
    </div>
  );
}

function DocFooter() {
  const { t } = useI18n();
  return (
    <footer
      style={{
        borderTop: "1px solid var(--rule)",
        padding: "28px clamp(20px, 5vw, 56px) 36px",
        maxWidth: 860,
        margin: "0 auto",
      }}
    >
      <div
        style={{
          display: "flex",
          justifyContent: "space-between",
          alignItems: "flex-start",
          gap: 20,
          flexWrap: "wrap",
        }}
      >
        <div style={{ maxWidth: 520 }}>
          <Wordmark size={15} />
          <p
            style={{
              fontSize: 12.5,
              color: "var(--ink-3)",
              marginTop: 10,
              lineHeight: 1.55,
            }}
            dangerouslySetInnerHTML={{ __html: t("landing.footer.disclaimer") }}
          />
          <div style={{ marginTop: 14, display: "flex", gap: 14, flexWrap: "wrap" }}>
            <FooterLink href="/legal" label={t("docs.nav.legal")} />
            <FooterLink href="/mcp" label={t("docs.nav.mcp")} />
            <FooterLink href="/api" label={t("docs.nav.api")} />
          </div>
        </div>
        <div
          className="mono"
          style={{
            fontSize: 11,
            color: "var(--ink-3)",
            textAlign: "right",
            lineHeight: 1.6,
          }}
        >
          <div>{t("landing.footer.copyright")}</div>
          <div>{t("landing.footer.legal")}</div>
          <div>anamnesa.kudaliar.id</div>
        </div>
      </div>
    </footer>
  );
}

function FooterLink({ href, label }: { href: string; label: string }) {
  return (
    <Link
      href={href}
      className="mono"
      style={{
        fontSize: 11,
        color: "var(--ink-2)",
        textDecoration: "none",
        letterSpacing: "0.08em",
        textTransform: "uppercase",
      }}
    >
      {label} →
    </Link>
  );
}

function BackLink({ label }: { label: string }) {
  return (
    <Link
      href="/"
      className="mono"
      style={{
        position: "fixed",
        bottom: 18,
        left: 18,
        padding: "8px 12px",
        background: "var(--paper-2)",
        border: "1px solid var(--rule)",
        borderRadius: 2,
        color: "var(--ink-2)",
        textDecoration: "none",
        fontSize: 11,
        letterSpacing: "0.08em",
        textTransform: "uppercase",
      }}
    >
      ← {label}
    </Link>
  );
}
