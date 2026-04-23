"use client";

import { useMemo, useState } from "react";
import Link from "next/link";
import { TopBar } from "@/components/shell/TopBar";
import { useHistory, type HistoryEntry } from "@/lib/useHistory";
import { useI18n } from "@/components/shell/LanguageProvider";

/**
 * Agent Track — list of past query runs reconstructed from the client's
 * local history (same source that powers /riwayat). Real trace events
 * only persist per-session on the server; this view surfaces what we
 * know from the stored FinalResponse (cached flag, citation count,
 * refusal reason) so the user has one place to review completed runs.
 */
export default function AgentTrackPage() {
  const history = useHistory();
  const { t } = useI18n();
  const [selectedId, setSelectedId] = useState<string | null>(null);

  const entries = history.entries;
  const selected = useMemo<HistoryEntry | null>(() => {
    if (!selectedId) return entries[0] ?? null;
    return entries.find((e) => e.id === selectedId) ?? null;
  }, [entries, selectedId]);

  return (
    <>
      <TopBar
        title={t("topbar.trace.title")}
        subtitle={`// ${t("topbar.trace.sub")}`}
      />
      <div className="agent-track-shell">
        <aside
          className="agent-track-list scroll-civic"
          style={{
            borderRight: "1px solid var(--rule)",
            background: "var(--paper-2)",
          }}
        >
          <div
            style={{
              padding: "14px 14px 10px",
              borderBottom: "1px solid var(--rule)",
            }}
          >
            <div className="label">{t("page.trace.runs_title")}</div>
            <div
              className="mono"
              style={{ fontSize: 10.5, color: "var(--ink-3)", marginTop: 4 }}
            >
              {entries.length} {t("page.trace.runs_sub")}
            </div>
          </div>
          {entries.length === 0 ? (
            <div
              className="mono"
              style={{
                fontSize: 11,
                color: "var(--ink-3)",
                padding: "20px 14px",
              }}
            >
              {t("page.trace.no_runs_html").split(/<a>|<\/a>/).map((part, i) =>
                i === 1 ? (
                  <Link key={i} href="/chat" style={{ color: "var(--navy)" }}>
                    {part}
                  </Link>
                ) : (
                  <span key={i}>{part}</span>
                ),
              )}
            </div>
          ) : (
            entries.map((e) => {
              const isSelected =
                (selected && e.id === selected.id) || (!selectedId && e === entries[0]);
              const status = e.final.refusal_reason
                ? "refused"
                : e.final.from_cache
                  ? "cached"
                  : "done";
              return (
                <button
                  key={e.id}
                  type="button"
                  onClick={() => setSelectedId(e.id)}
                  style={{
                    display: "block",
                    width: "100%",
                    padding: "12px 14px",
                    background: isSelected ? "var(--paper)" : "transparent",
                    borderLeft: isSelected
                      ? "2px solid var(--navy)"
                      : "2px solid transparent",
                    border: "none",
                    borderBottom: "1px solid var(--rule)",
                    textAlign: "left",
                    cursor: "pointer",
                  }}
                >
                  <div
                    style={{
                      display: "flex",
                      gap: 6,
                      marginBottom: 4,
                      alignItems: "center",
                    }}
                  >
                    <span
                      className="mono"
                      style={{ fontSize: 10.5, color: "var(--ink-3)" }}
                    >
                      {e.final.query_id.slice(0, 10)}
                    </span>
                    <span style={{ flex: 1 }} />
                    <StatusChip status={status} />
                  </div>
                  <div
                    style={{
                      fontSize: 12.5,
                      color: "var(--ink)",
                      marginBottom: 4,
                      overflow: "hidden",
                      textOverflow: "ellipsis",
                      whiteSpace: "nowrap",
                    }}
                  >
                    {e.query || "(tanpa teks kueri)"}
                  </div>
                  <div
                    className="mono"
                    style={{ fontSize: 10.5, color: "var(--ink-3)" }}
                  >
                    {formatAge(e.timestamp)} ·{" "}
                    {e.final.refusal_reason
                      ? "tanpa sitasi"
                      : `${e.final.citations.length} sitasi`}
                    {e.final.from_cache ? " · cache" : ""}
                  </div>
                </button>
              );
            })
          )}
        </aside>

        <div
          className="agent-track-detail scroll-civic"
          style={{ padding: "24px clamp(20px, 4vw, 36px)" }}
        >
          {selected ? <TraceDetail entry={selected} /> : <EmptyDetail />}
        </div>
      </div>
    </>
  );
}

function StatusChip({ status }: { status: "done" | "refused" | "cached" }) {
  const colors = {
    done: { c: "var(--current)", bg: "var(--current-bg)", label: "DONE" },
    refused: { c: "var(--oxblood)", bg: "var(--withdrawn-bg)", label: "REFUSED" },
    cached: { c: "var(--teal)", bg: "var(--paper-3)", label: "CACHE" },
  }[status];
  return (
    <span
      className="mono"
      style={{
        fontSize: 10,
        color: colors.c,
        background: colors.bg,
        padding: "1px 5px",
        letterSpacing: "0.06em",
      }}
    >
      {colors.label}
    </span>
  );
}

function TraceDetail({ entry }: { entry: HistoryEntry }) {
  const { t } = useI18n();
  const fin = entry.final;
  const refused = !!fin.refusal_reason;
  return (
    <div>
      <div style={{ display: "flex", alignItems: "baseline", gap: 14, marginBottom: 18, flexWrap: "wrap" }}>
        <span
          className="mono"
          style={{
            fontSize: 10.5,
            color: "var(--oxblood)",
            letterSpacing: "0.14em",
          }}
        >
          § RUN · {fin.query_id}
        </span>
        <div style={{ flex: 1, height: 1, background: "var(--rule)" }} />
        <span className="mono" style={{ fontSize: 11, color: "var(--ink-3)" }}>
          {new Date(entry.timestamp).toLocaleString("id-ID")}
        </span>
      </div>

      <h2
        className="display"
        style={{
          fontSize: 22,
          fontWeight: 500,
          margin: 0,
          letterSpacing: "-0.01em",
          lineHeight: 1.25,
        }}
      >
        {entry.query || "(tanpa teks kueri)"}
      </h2>

      <div
        style={{
          display: "grid",
          gridTemplateColumns: "repeat(auto-fit, minmax(160px, 1fr))",
          gap: 12,
          marginTop: 22,
        }}
      >
        <Stat
          label={t("page.trace.stat.status")}
          value={
            refused
              ? t("page.trace.status.refused")
              : fin.from_cache
                ? t("page.trace.status.cached")
                : t("page.trace.status.done")
          }
        />
        <Stat label={t("page.trace.stat.cites")} value={String(fin.citations.length)} />
        <Stat label={t("page.trace.stat.flags")} value={String(fin.currency_flags.length)} />
        <Stat
          label={t("page.trace.stat.cache")}
          value={
            fin.from_cache
              ? `${Math.round((fin.cached_age_s ?? 0) / 60)}m ago`
              : "—"
          }
        />
      </div>

      {refused && (
        <div
          style={{
            marginTop: 22,
            padding: "12px 14px",
            border: "1px solid var(--oxblood)",
            background: "var(--withdrawn-bg)",
            color: "var(--oxblood)",
            fontSize: 13,
            lineHeight: 1.55,
          }}
        >
          <div
            className="mono"
            style={{ fontSize: 10.5, letterSpacing: "0.12em", marginBottom: 4 }}
          >
            {t("page.trace.reason_label")}
          </div>
          {fin.refusal_reason}
        </div>
      )}

      <div style={{ marginTop: 24 }}>
        <div className="label" style={{ marginBottom: 10 }}>
          {t("page.trace.cites_summary")}
        </div>
        {fin.citations.length === 0 ? (
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
            {t("page.trace.no_cites")}
          </div>
        ) : (
          <ol style={{ listStyle: "none", padding: 0, margin: 0, display: "flex", flexDirection: "column", gap: 10 }}>
            {fin.citations.map((c, i) => (
              <li
                key={c.key}
                style={{
                  border: "1px solid var(--rule)",
                  background: "var(--paper-2)",
                  padding: "10px 14px 10px 18px",
                  position: "relative",
                  borderRadius: 2,
                }}
              >
                <span
                  className="mono"
                  style={{
                    position: "absolute",
                    top: 0,
                    left: 0,
                    background: "var(--navy)",
                    color: "var(--paper)",
                    padding: "1px 6px",
                    fontSize: 10.5,
                    fontWeight: 500,
                  }}
                >
                  {i + 1}
                </span>
                <div
                  style={{
                    fontSize: 13,
                    color: "var(--ink)",
                    fontWeight: 500,
                    marginTop: 2,
                    wordBreak: "break-all",
                  }}
                >
                  {c.doc_id}
                </div>
                <div
                  className="mono"
                  style={{ fontSize: 10.5, color: "var(--ink-3)", marginTop: 2 }}
                >
                  hal {c.page} · {c.section_slug}
                </div>
              </li>
            ))}
          </ol>
        )}
      </div>

      <p
        className="mono"
        style={{
          marginTop: 22,
          fontSize: 10.5,
          color: "var(--ink-3)",
          letterSpacing: "0.08em",
          lineHeight: 1.55,
        }}
      >
        {t("page.trace.footer_note")}
      </p>
    </div>
  );
}

function Stat({ label, value }: { label: string; value: string }) {
  return (
    <div
      style={{
        border: "1px solid var(--rule)",
        padding: "10px 12px",
        borderRadius: 2,
      }}
    >
      <div
        className="mono"
        style={{
          fontSize: 10,
          color: "var(--ink-3)",
          letterSpacing: "0.12em",
          textTransform: "uppercase",
          marginBottom: 4,
        }}
      >
        {label}
      </div>
      <div
        className="display"
        style={{ fontSize: 18, color: "var(--ink)", fontWeight: 500 }}
      >
        {value}
      </div>
    </div>
  );
}

function EmptyDetail() {
  const { t } = useI18n();
  return (
    <div
      style={{
        color: "var(--ink-3)",
        padding: "40px 0",
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
        {t("page.trace.pick_run_eyebrow")}
      </div>
      <p style={{ fontSize: 13.5, lineHeight: 1.55, maxWidth: 360, margin: "0 auto" }}>
        {t("page.trace.pick_run_body")}
      </p>
      <Link
        href="/chat"
        className="btn btn-primary"
        style={{
          marginTop: 18,
          padding: "7px 14px",
          fontSize: 12.5,
          display: "inline-flex",
        }}
      >
        {t("page.trace.new_run")}
      </Link>
    </div>
  );
}

function formatAge(ts: number): string {
  const diff = Date.now() - ts;
  const s = Math.floor(diff / 1000);
  if (s < 60) return "baru saja";
  const m = Math.floor(s / 60);
  if (m < 60) return `${m} menit lalu`;
  const h = Math.floor(m / 60);
  if (h < 24) return `${h} jam lalu`;
  const d = Math.floor(h / 24);
  return `${d} hari lalu`;
}
