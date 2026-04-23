"use client";

import { DocPage } from "@/components/docs/DocPage";
import { useI18n } from "@/components/shell/LanguageProvider";

export default function LegalPage() {
  const { t } = useI18n();
  return (
    <DocPage
      eyebrow={t("legal.eyebrow")}
      title={t("legal.title")}
      subtitle={t("legal.subtitle")}
    >
      <Section heading={t("legal.pasal42.heading")}>
        <div
          className="doc-prose"
          dangerouslySetInnerHTML={{ __html: t("legal.pasal42.body_html") }}
        />
      </Section>

      <Section heading={t("legal.consequences.heading")}>
        <div
          className="doc-prose"
          dangerouslySetInnerHTML={{ __html: t("legal.consequences.body_html") }}
        />
      </Section>

      <Section heading={t("legal.scope.heading")}>
        <div
          className="doc-prose"
          dangerouslySetInnerHTML={{ __html: t("legal.scope.body_html") }}
        />
      </Section>

      <div
        style={{
          marginTop: 32,
          padding: "14px 18px",
          borderLeft: "2px solid var(--oxblood)",
          background: "var(--paper-2)",
          fontSize: 13,
          color: "var(--ink-2)",
          lineHeight: 1.55,
        }}
      >
        {t("legal.note")}
      </div>
    </DocPage>
  );
}

function Section({
  heading,
  children,
}: {
  heading: string;
  children: React.ReactNode;
}) {
  return (
    <section style={{ marginTop: 36 }}>
      <h2
        className="display"
        style={{
          fontSize: "clamp(20px, 2.8vw, 26px)",
          margin: 0,
          fontWeight: 500,
          letterSpacing: "-0.01em",
          lineHeight: 1.2,
          color: "var(--ink)",
        }}
      >
        {heading}
      </h2>
      <div style={{ marginTop: 14 }}>{children}</div>
    </section>
  );
}
