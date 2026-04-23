"use client";

import { DocPage } from "@/components/docs/DocPage";
import { useI18n } from "@/components/shell/LanguageProvider";

const CONFIG_SNIPPET = `{
  "mcpServers": {
    "anamnesa": {
      "command": "python",
      "args": ["-m", "mcp.anamnesa_mcp"],
      "cwd": "/path/to/anamnesa",
      "env": {
        "ANAMNESA_INDEX_DIR": "/path/to/anamnesa/index",
        "ANAMNESA_PUBLIC_ORIGIN": "https://anamnesa.kudaliar.id"
      }
    }
  }
}`;

export default function McpPage() {
  const { t } = useI18n();
  return (
    <DocPage
      eyebrow={t("mcp.eyebrow")}
      title={t("mcp.title")}
      subtitle={t("mcp.subtitle")}
    >
      <Section heading={t("mcp.install.heading")}>
        <p style={{ fontSize: 14.5, lineHeight: 1.6, color: "var(--ink-2)", margin: 0 }}>
          {t("mcp.install.body")}
        </p>
        <CodeBlock code={CONFIG_SNIPPET} lang="json" />
        <p
          style={{
            fontSize: 13,
            color: "var(--ink-3)",
            marginTop: 12,
            lineHeight: 1.55,
          }}
        >
          {t("mcp.install.note")}
        </p>
      </Section>

      <Section heading={t("mcp.tools.heading")}>
        <div style={{ display: "flex", flexDirection: "column", gap: 14 }}>
          <ToolCard
            name={t("mcp.tools.search.name")}
            body={t("mcp.tools.search.body")}
          />
          <ToolCard
            name={t("mcp.tools.section.name")}
            body={t("mcp.tools.section.body")}
          />
          <ToolCard
            name={t("mcp.tools.pdf.name")}
            body={t("mcp.tools.pdf.body")}
          />
          <ToolCard
            name={t("mcp.tools.supersession.name")}
            body={t("mcp.tools.supersession.body")}
          />
        </div>
      </Section>

      <div
        style={{
          marginTop: 32,
          padding: "14px 18px",
          borderLeft: "2px solid var(--navy)",
          background: "var(--paper-2)",
          fontSize: 13,
          color: "var(--ink-2)",
          lineHeight: 1.55,
        }}
      >
        {t("mcp.license")}
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
          margin: "0 0 14px",
          fontWeight: 500,
          letterSpacing: "-0.01em",
          lineHeight: 1.2,
          color: "var(--ink)",
        }}
      >
        {heading}
      </h2>
      {children}
    </section>
  );
}

function ToolCard({ name, body }: { name: string; body: string }) {
  return (
    <div
      style={{
        padding: "14px 18px",
        background: "var(--paper-2)",
        border: "1px solid var(--rule)",
        borderLeft: "2px solid var(--navy)",
        borderRadius: 2,
      }}
    >
      <div
        className="mono"
        style={{
          fontSize: 13,
          color: "var(--ink)",
          fontWeight: 500,
          wordBreak: "break-all",
        }}
      >
        {name}
      </div>
      <p
        style={{
          fontSize: 13.5,
          color: "var(--ink-2)",
          margin: "8px 0 0",
          lineHeight: 1.6,
        }}
      >
        {body}
      </p>
    </div>
  );
}

function CodeBlock({ code, lang }: { code: string; lang?: string }) {
  return (
    <pre
      className="mono"
      style={{
        marginTop: 14,
        padding: "14px 16px",
        background: "var(--paper-3, var(--paper-2))",
        border: "1px solid var(--rule)",
        borderRadius: 2,
        overflow: "auto",
        fontSize: 12.5,
        lineHeight: 1.55,
        color: "var(--ink)",
      }}
      data-lang={lang}
    >
      {code}
    </pre>
  );
}
