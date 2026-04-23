"use client";

import { useCallback, type ReactNode } from "react";
import { useRouter } from "next/navigation";
import { TopBar } from "@/components/shell/TopBar";
import { CurrencyChip, type CurrencyKind } from "@/components/shell/CurrencyChip";
import { useFavorites } from "@/lib/useFavorites";
import { useI18n } from "@/components/shell/LanguageProvider";
import type { FinalResponse } from "@/lib/types";

export default function FavoritPage() {
  const router = useRouter();
  const fav = useFavorites();
  const { t } = useI18n();

  const openAnswer = useCallback(
    (entry: { query: string; final: FinalResponse }) => {
      try {
        window.sessionStorage.setItem(
          "anamnesa.restore_entry",
          JSON.stringify(entry),
        );
      } catch {
        // ignore
      }
      router.push("/chat");
    },
    [router],
  );

  return (
    <>
      <TopBar
        title={t("topbar.favorites.title")}
        subtitle={`// ${t("topbar.favorites.sub")}`}
      >
        {fav.total > 0 && (
          <button
            type="button"
            onClick={() => {
              if (confirm(t("page.favorites.clear_all") + "?")) fav.clearAll();
            }}
            className="btn btn-ghost"
            style={{ padding: "6px 10px", fontSize: 12 }}
          >
            {t("page.favorites.clear_all")}
          </button>
        )}
      </TopBar>

      <div className="mx-auto max-w-[1100px] px-4 md:px-6 lg:px-10 py-6 md:py-8">
        {fav.total === 0 ? (
          <EmptyState />
        ) : (
          <div style={{ display: "flex", flexDirection: "column", gap: 36 }}>
            <Section title={t("page.favorites.section_answers")} count={fav.answers.length}>
              {fav.answers.length === 0 ? (
                <EmptyInline label={t("page.favorites.empty_answers")} />
              ) : (
                <Grid>
                  {fav.answers.map((a) => (
                    <FavAnswerCard
                      key={a.id}
                      query={a.query}
                      final={a.final}
                      savedAt={a.saved_at}
                      onOpen={() => openAnswer({ query: a.query, final: a.final })}
                      onRemove={() => fav.remove("answer", a.id)}
                    />
                  ))}
                </Grid>
              )}
            </Section>

            <Section title={t("page.favorites.section_chunks")} count={fav.chunks.length}>
              {fav.chunks.length === 0 ? (
                <EmptyInline label={t("page.favorites.empty_chunks")} />
              ) : (
                <Grid>
                  {fav.chunks.map((c) => (
                    <FavChunkCard
                      key={c.id}
                      docId={c.doc_id}
                      page={c.page}
                      excerpt={c.chunk_text}
                      onRemove={() => fav.remove("chunk", c.id)}
                    />
                  ))}
                </Grid>
              )}
            </Section>

            <Section title={t("page.favorites.section_docs")} count={fav.docs.length}>
              {fav.docs.length === 0 ? (
                <EmptyInline label={t("page.favorites.empty_docs")} />
              ) : (
                <Grid>
                  {fav.docs.map((d) => (
                    <FavDocCard
                      key={d.id}
                      docId={d.id}
                      title={d.title}
                      sourceType={d.source_type}
                      year={d.year}
                      currency={currencyFromStatus(d.currency_status, d.year)}
                      onRemove={() => fav.remove("doc", d.id)}
                    />
                  ))}
                </Grid>
              )}
            </Section>
          </div>
        )}
      </div>
    </>
  );
}

function Section({
  title,
  count,
  children,
}: {
  title: string;
  count: number;
  children: ReactNode;
}) {
  return (
    <section>
      <div style={{ display: "flex", alignItems: "baseline", gap: 12, marginBottom: 14 }}>
        <h3
          className="display"
          style={{ fontSize: 20, fontWeight: 500, margin: 0, letterSpacing: "-0.01em" }}
        >
          {title}
        </h3>
        <span className="mono" style={{ fontSize: 11, color: "var(--ink-3)" }}>
          {count}
        </span>
        <div style={{ flex: 1, height: 1, background: "var(--rule)" }} />
      </div>
      {children}
    </section>
  );
}

function Grid({ children }: { children: ReactNode }) {
  return (
    <div
      style={{
        display: "grid",
        gridTemplateColumns: "repeat(auto-fill, minmax(280px, 1fr))",
        gap: 12,
      }}
    >
      {children}
    </div>
  );
}

function EmptyInline({ label }: { label: string }) {
  return (
    <div
      className="mono"
      style={{
        padding: "16px",
        fontSize: 11.5,
        color: "var(--ink-3)",
        border: "1px dashed var(--rule)",
        borderRadius: 2,
      }}
    >
      {label}
    </div>
  );
}

function EmptyState() {
  const { t } = useI18n();
  return (
    <div
      style={{
        padding: "48px 28px",
        border: "1px dashed var(--rule)",
        background: "var(--paper-2)",
        borderRadius: 2,
        color: "var(--ink-2)",
        textAlign: "center",
      }}
    >
      <div
        className="mono"
        style={{
          fontSize: 10.5,
          color: "var(--oxblood)",
          letterSpacing: "0.14em",
          marginBottom: 10,
        }}
      >
        {t("page.favorites.empty_eyebrow")}
      </div>
      <h2
        className="display"
        style={{ fontSize: 24, margin: 0, fontWeight: 500, letterSpacing: "-0.01em" }}
      >
        {t("page.favorites.empty_title")}
      </h2>
      <p
        style={{
          marginTop: 12,
          fontSize: 13,
          maxWidth: 420,
          margin: "12px auto 0",
          lineHeight: 1.55,
        }}
        dangerouslySetInnerHTML={{ __html: t("page.favorites.empty_body_html") }}
      />
    </div>
  );
}

function FavAnswerCard({
  query,
  final,
  savedAt,
  onOpen,
  onRemove,
}: {
  query: string;
  final: FinalResponse;
  savedAt: number;
  onOpen: () => void;
  onRemove: () => void;
}) {
  const citations = final.citations.length;
  const refused = final.refusal_reason;
  const snippet = final.answer_markdown.replace(/\[\[[^\]]+\]\]/g, "").slice(0, 180);
  return (
    <article
      style={{
        background: "var(--paper-2)",
        border: "1px solid var(--rule)",
        padding: "12px 14px",
        borderRadius: 2,
        display: "flex",
        flexDirection: "column",
        gap: 8,
      }}
    >
      <div style={{ display: "flex", gap: 8, alignItems: "center" }}>
        <span style={{ color: "var(--aging)", fontSize: 14 }}>★</span>
        <span className="mono" style={{ fontSize: 10.5, color: "var(--ink-3)", flex: 1 }}>
          Q · {formatAge(savedAt)}
        </span>
        <RemoveBtn onClick={onRemove} />
      </div>
      <div
        style={{
          fontSize: 13.5,
          color: "var(--ink)",
          fontWeight: 500,
          lineHeight: 1.4,
          fontStyle: "italic",
        }}
      >
        {query || "(tanpa teks pertanyaan)"}
      </div>
      <div
        style={{
          fontSize: 12,
          color: refused ? "var(--oxblood)" : "var(--ink-2)",
          lineHeight: 1.5,
        }}
      >
        {snippet}
        {snippet.length >= 180 ? "…" : ""}
      </div>
      <div
        style={{
          display: "flex",
          alignItems: "center",
          gap: 8,
          marginTop: "auto",
          paddingTop: 8,
          borderTop: "1px dashed var(--rule)",
        }}
      >
        <span className="mono" style={{ fontSize: 10.5, color: "var(--ink-3)", flex: 1 }}>
          {refused ? "penolakan" : `${citations} sitasi`}
        </span>
        <button
          type="button"
          onClick={onOpen}
          className="btn btn-ghost"
          style={{ padding: "4px 8px", fontSize: 11.5 }}
        >
          Buka →
        </button>
      </div>
    </article>
  );
}

function FavChunkCard({
  docId,
  page,
  excerpt,
  onRemove,
}: {
  docId: string;
  page: number;
  excerpt: string;
  onRemove: () => void;
}) {
  return (
    <article
      style={{
        background: "var(--paper-2)",
        border: "1px solid var(--rule)",
        padding: "12px 14px",
        borderRadius: 2,
      }}
    >
      <div style={{ display: "flex", gap: 8, marginBottom: 6, alignItems: "center" }}>
        <span style={{ color: "var(--aging)", fontSize: 14 }}>★</span>
        <span className="mono" style={{ fontSize: 10.5, color: "var(--ink-3)", flex: 1 }}>
          ¶ kutipan · hal. {page}
        </span>
        <RemoveBtn onClick={onRemove} />
      </div>
      <div
        className="mono"
        style={{
          fontSize: 11.5,
          color: "var(--ink)",
          fontWeight: 500,
          wordBreak: "break-all",
        }}
      >
        {docId}
      </div>
      <div
        style={{
          fontSize: 12,
          color: "var(--ink-2)",
          lineHeight: 1.5,
          fontStyle: "italic",
          marginTop: 6,
          paddingLeft: 8,
          borderLeft: "2px solid var(--rule-2)",
        }}
      >
        “{excerpt}”
      </div>
    </article>
  );
}

function FavDocCard({
  docId,
  title,
  sourceType,
  year,
  currency,
  onRemove,
}: {
  docId: string;
  title: string;
  sourceType: string;
  year: number;
  currency: CurrencyKind;
  onRemove: () => void;
}) {
  return (
    <article
      style={{
        background: "var(--paper-2)",
        border: "1px solid var(--rule)",
        padding: "12px 14px",
        borderRadius: 2,
        display: "flex",
        alignItems: "center",
        gap: 10,
      }}
    >
      <span style={{ color: "var(--aging)", fontSize: 14 }}>★</span>
      <div style={{ flex: 1, minWidth: 0 }}>
        <div style={{ fontSize: 13, color: "var(--ink)", fontWeight: 500 }}>{title}</div>
        <div className="mono" style={{ fontSize: 10.5, color: "var(--ink-3)", marginTop: 2, overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>
          {docId} · {sourceType} · {year}
        </div>
      </div>
      <CurrencyChip kind={currency} />
      <RemoveBtn onClick={onRemove} />
    </article>
  );
}

function RemoveBtn({ onClick }: { onClick: () => void }) {
  return (
    <button
      type="button"
      onClick={onClick}
      aria-label="Hapus dari favorit"
      title="Hapus"
      style={{
        background: "transparent",
        border: "none",
        cursor: "pointer",
        color: "var(--ink-4)",
        padding: 2,
        display: "flex",
        alignItems: "center",
        fontSize: 14,
      }}
    >
      ×
    </button>
  );
}

function currencyFromStatus(s?: string, year?: number): CurrencyKind {
  if (s === "withdrawn") return "withdrawn";
  if (s === "superseded") return "superseded";
  if (s === "aging") return "aging";
  if (year && year <= new Date().getFullYear() - 5) return "aging";
  return "current";
}

function formatAge(ms: number): string {
  const diff = Date.now() - ms;
  const s = Math.floor(diff / 1000);
  if (s < 60) return "baru saja";
  const m = Math.floor(s / 60);
  if (m < 60) return `${m} menit lalu`;
  const h = Math.floor(m / 60);
  if (h < 24) return `${h} jam lalu`;
  const d = Math.floor(h / 24);
  return `${d} hari lalu`;
}
