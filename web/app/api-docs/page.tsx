"use client";

import { DocPage } from "@/components/docs/DocPage";
import { useI18n } from "@/components/shell/LanguageProvider";

const BASE_URL = "https://anamnesa.kudaliar.id";

const CURL_QUERY = `curl -X POST ${BASE_URL}/api/query \\
  -H 'Content-Type: application/json' \\
  -d '{
    "query": "DBD derajat II dewasa, kapan dirujuk dari Puskesmas?",
    "prior_query": null,
    "prior_answer": null
  }'
# → {"query_id":"01K…","stream_url":"/api/stream/01K…"}`;

const CURL_STREAM = `curl -N ${BASE_URL}/api/stream/01K…
# event: trace
# data: {"agent":"normalizer","event_type":"normalized",…}
# event: partial
# data: {"seq":1,"delta":"Pasien DBD derajat II…"}
# event: final
# data: {"answer_markdown":"…","citations":[…]}`;

const CURL_SEARCH = `curl '${BASE_URL}/api/search?q=dengue+anak&top_k=5&method=hybrid'
# → {"hits":[{doc_id, page, section_slug, text, score, …}]}`;

const CURL_DRUG = `curl '${BASE_URL}/api/drug-lookup?q=amoksisilin&limit=15'
# → {query, matched_query, translit_used, doc_id, doc_title,
#    source_url, total_hits, total_pages, results:[…]}

curl '${BASE_URL}/api/drug-mentions?q=amoksisilin&limit=12'
# → same query across every non-Fornas guideline,
#   grouped by doc.`;

const CURL_GUIDELINE = `curl ${BASE_URL}/api/guideline/pnpk-dengue-anak-2021.html
# → self-contained HTML, no external deps

curl ${BASE_URL}/api/guideline/pnpk-dengue-anak-2021.md
# → Markdown, suitable for offline reading`;

export default function ApiPage() {
  const { t } = useI18n();
  return (
    <DocPage
      eyebrow={t("api.eyebrow")}
      title={t("api.title")}
      subtitle={t("api.subtitle")}
    >
      <Section heading={t("api.base.heading")}>
        <p style={{ fontSize: 14.5, color: "var(--ink-2)", margin: 0, lineHeight: 1.6 }}>
          {t("api.base.body")}
        </p>
        <div
          className="mono"
          style={{
            marginTop: 10,
            padding: "8px 12px",
            background: "var(--paper-2)",
            border: "1px solid var(--rule)",
            borderRadius: 2,
            fontSize: 14,
            color: "var(--navy)",
          }}
        >
          {BASE_URL}
        </div>
      </Section>

      <Section
        heading={t("api.query.heading")}
        method="POST"
        path="/api/query"
      >
        <p style={{ fontSize: 14.5, color: "var(--ink-2)", margin: "0 0 12px", lineHeight: 1.6 }}>
          {t("api.query.body")}
        </p>
        <CodeBlock code={CURL_QUERY} />
      </Section>

      <Section
        heading={t("api.stream.heading")}
        method="GET"
        path="/api/stream/{query_id}"
      >
        <p style={{ fontSize: 14.5, color: "var(--ink-2)", margin: "0 0 12px", lineHeight: 1.6 }}>
          {t("api.stream.body")}
        </p>
        <CodeBlock code={CURL_STREAM} />
      </Section>

      <Section
        heading={t("api.search.heading")}
        method="GET"
        path="/api/search"
      >
        <p style={{ fontSize: 14.5, color: "var(--ink-2)", margin: "0 0 12px", lineHeight: 1.6 }}>
          {t("api.search.body")}
        </p>
        <CodeBlock code={CURL_SEARCH} />
      </Section>

      <Section
        heading={t("api.drug.heading")}
        method="GET"
        path="/api/drug-lookup · /api/drug-mentions"
      >
        <p style={{ fontSize: 14.5, color: "var(--ink-2)", margin: "0 0 12px", lineHeight: 1.6 }}>
          {t("api.drug.body")}
        </p>
        <CodeBlock code={CURL_DRUG} />
      </Section>

      <Section
        heading={t("api.guideline.heading")}
        method="GET"
        path="/api/guideline/{doc_id}.(html|md)"
      >
        <p style={{ fontSize: 14.5, color: "var(--ink-2)", margin: "0 0 12px", lineHeight: 1.6 }}>
          {t("api.guideline.body")}
        </p>
        <CodeBlock code={CURL_GUIDELINE} />
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
        {t("api.stability")}
      </div>
    </DocPage>
  );
}

function Section({
  heading,
  method,
  path,
  children,
}: {
  heading: string;
  method?: string;
  path?: string;
  children: React.ReactNode;
}) {
  return (
    <section style={{ marginTop: 40 }}>
      <div
        style={{
          display: "flex",
          alignItems: "baseline",
          gap: 14,
          flexWrap: "wrap",
          marginBottom: 14,
        }}
      >
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
        {method && path && (
          <div
            className="mono"
            style={{
              display: "inline-flex",
              alignItems: "center",
              gap: 8,
              padding: "3px 8px",
              background: "var(--paper-2)",
              border: "1px solid var(--rule)",
              borderRadius: 2,
              fontSize: 11.5,
            }}
          >
            <span style={{ color: "var(--navy)", fontWeight: 600 }}>{method}</span>
            <span style={{ color: "var(--ink-2)" }}>{path}</span>
          </div>
        )}
      </div>
      {children}
    </section>
  );
}

function CodeBlock({ code }: { code: string }) {
  return (
    <pre
      className="mono"
      style={{
        margin: 0,
        padding: "14px 16px",
        background: "var(--paper-3, var(--paper-2))",
        border: "1px solid var(--rule)",
        borderRadius: 2,
        overflow: "auto",
        fontSize: 12.5,
        lineHeight: 1.55,
        color: "var(--ink)",
      }}
    >
      {code}
    </pre>
  );
}
