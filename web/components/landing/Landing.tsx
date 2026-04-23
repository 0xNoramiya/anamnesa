"use client";

import Link from "next/link";
import { Wordmark } from "@/components/shell/Logo";
import { CurrencyChip } from "@/components/shell/CurrencyChip";
import { useI18n } from "@/components/shell/LanguageProvider";
import { LANG_LABELS, type Lang } from "@/lib/i18n";

/**
 * Landing page — five tight blocks:
 *   Hero → Feature bullets → One demo → Legal basis → CTA band → Footer
 *
 * Bahasa / English toggle in the top bar keeps clinical content Bahasa
 * where it represents the actual corpus (medical terms), and switches
 * all chrome copy to English when judges select it.
 */
export function Landing() {
  return (
    <div style={{ background: "var(--paper)", color: "var(--ink)", minHeight: "100vh" }}>
      <LandingHeader />
      <LandingHero />
      <LandingFeatures />
      <LandingDemo />
      <LandingLegal />
      <LandingCTA />
      <LandingFooter />
    </div>
  );
}

function LandingHeader() {
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
      <Wordmark size={15} />
      <div style={{ flex: 1 }} />
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

function LandingHero() {
  const { t } = useI18n();
  return (
    <section
      style={{
        padding: "clamp(48px, 9vw, 96px) clamp(20px, 5vw, 56px) clamp(32px, 6vw, 56px)",
        maxWidth: 1200,
        margin: "0 auto",
      }}
    >
      <h1
        className="display"
        style={{
          fontSize: "clamp(34px, 6.5vw, 64px)",
          lineHeight: 1.05,
          margin: 0,
          fontWeight: 500,
          letterSpacing: "-0.025em",
          color: "var(--ink)",
          fontVariationSettings: "'opsz' 60, 'SOFT' 30",
          maxWidth: 900,
        }}
      >
        {t("landing.hero.h1.line1")}
        <br />
        <span style={{ fontStyle: "italic", color: "var(--navy)" }}>
          {t("landing.hero.h1.line2")}
        </span>
      </h1>

      <p
        style={{
          fontSize: "clamp(16px, 2.2vw, 19px)",
          lineHeight: 1.55,
          marginTop: 22,
          color: "var(--ink-2)",
          maxWidth: 640,
          fontWeight: 400,
        }}
      >
        {t("landing.hero.sub")}
      </p>

      <div
        style={{
          display: "flex",
          gap: 10,
          marginTop: 28,
          alignItems: "center",
          flexWrap: "wrap",
        }}
      >
        <Link
          href="/chat"
          className="btn btn-primary"
          style={{ padding: "12px 20px", fontSize: 14 }}
        >
          {t("landing.cta.open")}
        </Link>
        <a
          href="#contoh"
          className="btn btn-ghost"
          style={{ padding: "12px 20px", fontSize: 14 }}
        >
          {t("landing.cta.example")}
        </a>
      </div>

      <p
        className="mono"
        style={{
          marginTop: 28,
          fontSize: 12,
          color: "var(--ink-3)",
          letterSpacing: "0.03em",
          lineHeight: 1.6,
          maxWidth: 540,
        }}
        dangerouslySetInnerHTML={{ __html: t("landing.hero.stat") }}
      />
    </section>
  );
}

function LandingFeatures() {
  const { t } = useI18n();
  const items = [
    { title: t("landing.features.cited.title"), body: t("landing.features.cited.body") },
    { title: t("landing.features.flags.title"), body: t("landing.features.flags.body") },
    { title: t("landing.features.refuse.title"), body: t("landing.features.refuse.body") },
    { title: t("landing.features.multiturn.title"), body: t("landing.features.multiturn.body") },
    { title: t("landing.features.fornas.title"), body: t("landing.features.fornas.body") },
  ];

  return (
    <section
      style={{
        padding: "clamp(32px, 5vw, 56px) clamp(20px, 5vw, 56px)",
        maxWidth: 1200,
        margin: "0 auto",
        borderTop: "1px solid var(--rule)",
      }}
    >
      <div
        style={{
          display: "grid",
          // 5 items: 3+2 on wide, 2+2+1 on tablet, 1 per row on narrow.
          gridTemplateColumns: "repeat(auto-fit, minmax(260px, 1fr))",
          gap: 20,
        }}
      >
        {items.map((it) => (
          <div
            key={it.title}
            style={{
              padding: "18px 20px",
              background: "var(--paper-2)",
              borderLeft: "2px solid var(--navy)",
            }}
          >
            <h3
              className="display"
              style={{
                fontSize: 18,
                fontWeight: 500,
                margin: 0,
                letterSpacing: "-0.01em",
                color: "var(--ink)",
              }}
            >
              {it.title}
            </h3>
            <p
              style={{
                fontSize: 13.5,
                color: "var(--ink-2)",
                lineHeight: 1.55,
                marginTop: 6,
              }}
            >
              {it.body}
            </p>
          </div>
        ))}
      </div>
    </section>
  );
}

function LandingDemo() {
  const { t } = useI18n();
  return (
    <section
      id="contoh"
      style={{
        padding: "clamp(40px, 6vw, 72px) clamp(20px, 5vw, 56px)",
        maxWidth: 1200,
        margin: "0 auto",
        borderTop: "1px solid var(--rule)",
      }}
    >
      <div style={{ maxWidth: 680, marginBottom: 28 }}>
        <div
          className="mono"
          style={{
            fontSize: 10.5,
            color: "var(--oxblood)",
            letterSpacing: "0.14em",
            marginBottom: 10,
          }}
        >
          {t("landing.demo.eyebrow")}
        </div>
        <h2
          className="display"
          style={{
            fontSize: "clamp(26px, 3.6vw, 36px)",
            margin: 0,
            fontWeight: 500,
            letterSpacing: "-0.02em",
            lineHeight: 1.15,
            color: "var(--ink)",
          }}
        >
          {t("landing.demo.h2")}
        </h2>
      </div>

      <div
        style={{
          background: "var(--paper-2)",
          border: "1px solid var(--rule)",
          borderRadius: 2,
          boxShadow: "0 1px 0 var(--rule-2), 0 14px 30px -18px rgba(15,27,45,0.14)",
          maxWidth: 820,
        }}
      >
        <div style={{ padding: "18px 22px", borderBottom: "1px solid var(--rule)" }}>
          <div className="label" style={{ marginBottom: 6 }}>
            {t("landing.demo.q_label")}
          </div>
          <div style={{ fontSize: 15, color: "var(--ink)", lineHeight: 1.5 }}>
            {t("landing.demo.q")}
          </div>
        </div>

        <div style={{ padding: "18px 22px" }}>
          <div className="label" style={{ marginBottom: 8 }}>
            {t("landing.demo.a_label")}
          </div>
          <div
            style={{
              fontSize: 15,
              lineHeight: 1.65,
              color: "var(--ink)",
            }}
            dangerouslySetInnerHTML={{
              __html: t("landing.demo.a_html").replace(
                /<sup>\[(\d+)\]<\/sup>/g,
                (_m, n) => `<span class="cite">${n}</span>`,
              ),
            }}
          />

          <div
            style={{
              marginTop: 14,
              display: "flex",
              gap: 8,
              flexWrap: "wrap",
              alignItems: "center",
            }}
          >
            <CurrencyChip kind="current" year={2023} />
            <span
              className="mono"
              style={{ fontSize: 10.5, color: "var(--ink-3)" }}
            >
              {t("landing.demo.meta")}
            </span>
          </div>

          <div
            style={{
              marginTop: 16,
              display: "flex",
              flexDirection: "column",
              gap: 8,
            }}
          >
            <MiniRef
              n={1}
              doc="PPK FKTP 2023 · Demam Berdarah Dengue"
              page="hal. 142"
            />
            <MiniRef
              n={2}
              doc="PPK FKTP 2023 · Demam Berdarah Dengue"
              page="hal. 145"
            />
          </div>
        </div>

        {/* Follow-up turn — visualizes the multi-turn flow inside the same
            card so judges see the feature without clicking through. */}
        <div
          style={{
            display: "flex",
            alignItems: "center",
            gap: 10,
            padding: "0 22px",
          }}
        >
          <div style={{ flex: 1, height: 1, background: "var(--rule)" }} />
          <span
            className="mono"
            style={{
              fontSize: 10,
              color: "var(--ink-3)",
              letterSpacing: "0.16em",
              padding: "2px 0",
            }}
          >
            {t("landing.demo.followup_label")}
          </span>
          <div style={{ flex: 1, height: 1, background: "var(--rule)" }} />
        </div>

        <div
          style={{
            padding: "16px 22px",
            borderBottom: "1px solid var(--rule)",
            display: "flex",
            alignItems: "flex-start",
            gap: 12,
          }}
        >
          <span
            className="mono"
            style={{
              fontSize: 10,
              color: "var(--navy)",
              letterSpacing: "0.12em",
              paddingTop: 3,
              minWidth: 28,
            }}
          >
            Q2
          </span>
          <div style={{ flex: 1 }}>
            <div
              className="label"
              style={{ marginBottom: 4, color: "var(--ink-3)" }}
            >
              {t("landing.demo.q_label")}
            </div>
            <div
              style={{
                fontSize: 15,
                color: "var(--ink)",
                lineHeight: 1.5,
                fontStyle: "italic",
              }}
            >
              {t("landing.demo.q2")}
            </div>
          </div>
        </div>

        <div style={{ padding: "18px 22px" }}>
          <div className="label" style={{ marginBottom: 8 }}>
            {t("landing.demo.a_label")}
          </div>
          <div
            style={{
              fontSize: 15,
              lineHeight: 1.65,
              color: "var(--ink)",
            }}
            dangerouslySetInnerHTML={{
              __html: t("landing.demo.a2_html").replace(
                /<sup>\[(\d+)\]<\/sup>/g,
                (_m, n) => `<span class="cite">${n}</span>`,
              ),
            }}
          />

          <div
            style={{
              marginTop: 14,
              display: "flex",
              gap: 8,
              flexWrap: "wrap",
              alignItems: "center",
            }}
          >
            <CurrencyChip kind="current" year={2021} />
            <span
              className="mono"
              style={{ fontSize: 10.5, color: "var(--ink-3)" }}
            >
              {t("landing.demo.meta2")}
            </span>
          </div>

          <div style={{ marginTop: 16 }}>
            <MiniRef
              n={3}
              doc="PNPK Dengue Anak 2021 · Warning signs"
              page="hal. 9"
            />
          </div>
        </div>
      </div>
    </section>
  );
}

function MiniRef({ n, doc, page }: { n: number; doc: string; page: string }) {
  return (
    <div
      style={{
        display: "flex",
        alignItems: "center",
        gap: 10,
        padding: "7px 10px",
        background: "var(--paper)",
        border: "1px solid var(--rule)",
        borderRadius: 2,
        fontSize: 12,
      }}
    >
      <span
        className="mono"
        style={{
          background: "var(--navy)",
          color: "var(--paper)",
          padding: "1px 6px",
          fontSize: 10.5,
          fontWeight: 500,
          flexShrink: 0,
        }}
      >
        {n}
      </span>
      <span
        style={{
          flex: 1,
          color: "var(--ink)",
          minWidth: 0,
          overflow: "hidden",
          textOverflow: "ellipsis",
          whiteSpace: "nowrap",
        }}
      >
        {doc}
      </span>
      <span
        className="mono"
        style={{ fontSize: 10.5, color: "var(--ink-3)", flexShrink: 0 }}
      >
        {page}
      </span>
    </div>
  );
}

function LandingLegal() {
  const { t } = useI18n();
  return (
    <section
      style={{
        padding: "clamp(32px, 5vw, 56px) clamp(20px, 5vw, 56px)",
        maxWidth: 1200,
        margin: "0 auto",
        borderTop: "1px solid var(--rule)",
      }}
    >
      <div
        style={{
          padding: "18px 22px",
          borderLeft: "2px solid var(--oxblood)",
          background: "var(--paper-2)",
          maxWidth: 780,
        }}
      >
        <div
          className="mono"
          style={{
            fontSize: 10.5,
            color: "var(--oxblood)",
            letterSpacing: "0.12em",
            marginBottom: 6,
          }}
        >
          {t("landing.legal.eyebrow")}
        </div>
        <p
          style={{
            fontSize: 14,
            color: "var(--ink-2)",
            lineHeight: 1.6,
            margin: 0,
          }}
          dangerouslySetInnerHTML={{ __html: t("landing.legal.body_html") }}
        />
      </div>
    </section>
  );
}

function LandingCTA() {
  const { t } = useI18n();
  return (
    <section
      style={{
        padding: "clamp(40px, 6vw, 72px) clamp(20px, 5vw, 56px)",
        maxWidth: 1200,
        margin: "0 auto",
        borderTop: "1px solid var(--rule)",
      }}
    >
      <div
        style={{
          background: "var(--ink)",
          color: "var(--paper)",
          padding: "clamp(28px, 5vw, 48px)",
          borderRadius: 2,
          display: "grid",
          gridTemplateColumns: "minmax(0, 1.5fr) minmax(0, 1fr)",
          gap: "clamp(20px, 4vw, 40px)",
          alignItems: "center",
        }}
        className="landing-cta-grid"
      >
        <div>
          <h2
            className="display"
            style={{
              fontSize: "clamp(22px, 3.2vw, 32px)",
              margin: 0,
              fontWeight: 500,
              letterSpacing: "-0.02em",
              lineHeight: 1.15,
            }}
          >
            {t("landing.cta_band.h2")}
          </h2>
          <p
            style={{
              fontSize: 14,
              color: "var(--paper-3)",
              opacity: 0.85,
              marginTop: 10,
              lineHeight: 1.55,
              maxWidth: 520,
            }}
          >
            {t("landing.cta_band.sub")}
          </p>
        </div>
        <div style={{ display: "flex", flexDirection: "column", gap: 8 }}>
          <Link
            href="/chat"
            className="btn btn-primary"
            style={{
              background: "var(--paper)",
              color: "var(--ink)",
              padding: "13px 18px",
              fontSize: 14,
              justifyContent: "center",
            }}
          >
            {t("landing.cta.open")}
          </Link>
          <Link
            href="/guideline"
            className="btn btn-ghost"
            style={{
              borderColor: "var(--ink-3)",
              color: "var(--paper)",
              padding: "13px 18px",
              fontSize: 14,
              justifyContent: "center",
            }}
          >
            {t("landing.cta.explore")}
          </Link>
        </div>
      </div>
    </section>
  );
}

function LandingFooter() {
  const { t } = useI18n();
  return (
    <footer
      style={{
        borderTop: "1px solid var(--rule)",
        padding: "28px clamp(20px, 5vw, 56px) 36px",
        maxWidth: 1200,
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
        <div style={{ maxWidth: 480 }}>
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
