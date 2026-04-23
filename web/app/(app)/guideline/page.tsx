"use client";

import { useEffect, useMemo, useState } from "react";
import { TopBar } from "@/components/shell/TopBar";
import {
  CurrencyChip,
  type CurrencyKind,
} from "@/components/shell/CurrencyChip";
import { PdfViewer } from "@/components/PdfViewer";
import { useRouter } from "next/navigation";
import { useFavorites } from "@/lib/useFavorites";
import { useI18n } from "@/components/shell/LanguageProvider";

const API_BASE = process.env.NEXT_PUBLIC_ANAMNESA_API ?? "";

interface ManifestSummary {
  schema_version: string;
  total: number;
  by_status: Record<string, number>;
  by_source_type: Record<string, number>;
}

type SourceType = "ppk_fktp" | "pnpk" | "kemkes_program" | "fornas" | "pedoman_fktp_ops" | "other";

interface DocumentLite {
  doc_id: string;
  title: string;
  source_type: SourceType;
  year: number;
  currency_status?: string;
}

const SOURCE_LABEL: Record<string, string> = {
  ppk_fktp: "PPK FKTP",
  pnpk: "PNPK",
  kemkes_program: "Kemenkes",
  fornas: "Fornas",
  pedoman_fktp_ops: "Pedoman FKTP",
  other: "Lain",
};

function currencyFromStatus(s?: string, year?: number): CurrencyKind {
  if (s === "withdrawn") return "withdrawn";
  if (s === "superseded") return "superseded";
  if (s === "aging") return "aging";
  if (year && year <= new Date().getFullYear() - 5) return "aging";
  return "current";
}

export default function GuidelinePage() {
  const router = useRouter();
  const { t } = useI18n();
  const [meta, setMeta] = useState<ManifestSummary | null>(null);
  const [docs, setDocs] = useState<DocumentLite[]>([]);
  const [loading, setLoading] = useState(true);
  const [typeFilter, setTypeFilter] = useState<string>("all");
  const [search, setSearch] = useState("");
  const [selected, setSelected] = useState<string | null>(null);
  const [pdfDoc, setPdfDoc] = useState<string | null>(null);

  useEffect(() => {
    const ac = new AbortController();
    (async () => {
      try {
        const [metaRes, docsRes] = await Promise.all([
          fetch(`${API_BASE.replace(/\/$/, "")}/api/manifest`, { signal: ac.signal }),
          fetch(`${API_BASE.replace(/\/$/, "")}/api/manifest?full=1`, { signal: ac.signal }),
        ]);
        if (metaRes.ok) setMeta(await metaRes.json());
        if (docsRes.ok) {
          const body = await docsRes.json();
          // /api/manifest in its default shape returns aggregates only,
          // but some deployments also respond to ?full=1 with a
          // `documents` array. If missing, we fall back to /api/search
          // distinct doc_ids below.
          if (Array.isArray(body.documents)) {
            setDocs(body.documents as DocumentLite[]);
          }
        }
      } catch {
        // Network hiccup — leave arrays empty; UI shows an empty state.
      } finally {
        setLoading(false);
      }
    })();
    return () => ac.abort();
  }, []);

  const filtered = useMemo(() => {
    const q = search.trim().toLowerCase();
    return docs.filter((d) => {
      if (typeFilter !== "all" && d.source_type !== typeFilter) return false;
      if (q && !d.title.toLowerCase().includes(q) && !d.doc_id.toLowerCase().includes(q)) {
        return false;
      }
      return true;
    });
  }, [docs, typeFilter, search]);

  const selectedDoc = selected ? docs.find((d) => d.doc_id === selected) ?? null : null;

  const askAbout = (docId: string) => {
    try {
      window.sessionStorage.setItem(
        "anamnesa.prefill_query",
        `Ringkaskan isi utama dokumen ${docId}.`,
      );
    } catch {}
    router.push("/chat");
  };

  return (
    <>
      <TopBar
        title={t("topbar.guideline.title")}
        subtitle={`// ${t("topbar.guideline.sub")}`}
      />
      <div className="guideline-shell">
        {/* Filters */}
        <aside
          className="guideline-filters scroll-civic"
          style={{
            borderRight: "1px solid var(--rule)",
            background: "var(--paper-2)",
            padding: "20px 18px",
            flexShrink: 0,
          }}
        >
          <div className="label" style={{ marginBottom: 10 }}>
            Jenis sumber
          </div>
          {[
            { k: "all", l: "Semua" },
            { k: "ppk_fktp", l: "PPK FKTP" },
            { k: "pnpk", l: "PNPK" },
            { k: "kemkes_program", l: "Kemenkes" },
          ].map((row) => (
            <FilterRow
              key={row.k}
              label={row.l}
              count={
                row.k === "all"
                  ? docs.length
                  : meta?.by_source_type?.[row.k] ?? 0
              }
              active={typeFilter === row.k}
              onClick={() => setTypeFilter(row.k)}
            />
          ))}

          <div className="label" style={{ margin: "20px 0 10px" }}>
            Masa berlaku
          </div>
          {(
            [
              { k: "current", l: "Berlaku", color: "var(--current)" },
              { k: "aging", l: "Perlu tinjau", color: "var(--aging)" },
              { k: "superseded", l: "Sudah diganti", color: "var(--superseded)" },
              { k: "withdrawn", l: "Dicabut", color: "var(--withdrawn)" },
            ] as const
          ).map((row) => (
            <FilterRow
              key={row.k}
              label={row.l}
              count={
                docs.filter(
                  (d) => currencyFromStatus(d.currency_status, d.year) === row.k,
                ).length
              }
              dot={row.color}
              onClick={() => {}}
            />
          ))}
        </aside>

        {/* List */}
        <div
          className="guideline-list scroll-civic"
          style={{
            minWidth: 0,
            borderRight: "1px solid var(--rule)",
            overflowY: "auto",
          }}
        >
          <div
            style={{
              padding: "16px 28px",
              borderBottom: "1px solid var(--rule)",
              display: "flex",
              alignItems: "center",
              gap: 12,
              position: "sticky",
              top: 0,
              background: "var(--paper)",
              zIndex: 2,
            }}
          >
            <div style={{ flex: 1 }}>
              <div className="mono" style={{ fontSize: 11, color: "var(--ink-2)" }}>
                <strong style={{ color: "var(--ink)" }}>
                  {loading ? "…" : `${filtered.length} dokumen`}
                </strong>
                {meta ? ` · dari ${meta.total}` : ""}
              </div>
            </div>
            <input
              placeholder="Saring judul…"
              value={search}
              onChange={(e) => setSearch(e.target.value)}
              style={{
                padding: "6px 10px",
                fontSize: 12.5,
                border: "1px solid var(--rule)",
                background: "var(--paper)",
                color: "var(--ink)",
                width: 200,
                fontFamily: "var(--font-body-stack)",
                outline: "none",
                borderRadius: 2,
              }}
            />
          </div>

          <div
            className="guideline-row-head label"
            style={{
              padding: "10px 20px",
              background: "var(--paper-2)",
              borderBottom: "1px solid var(--rule)",
            }}
          >
            <div>Judul</div>
            <div className="guideline-list-cell-sm">Jenis</div>
            <div className="guideline-list-cell-sm">Tahun</div>
            <div>Status</div>
          </div>

          {loading && (
            <div style={{ padding: 28, color: "var(--ink-3)" }}>
              Memuat pustaka…
            </div>
          )}

          {!loading && docs.length === 0 && (
            <div style={{ padding: 28, color: "var(--ink-3)", fontSize: 13.5 }}>
              Endpoint <code>/api/manifest?full=1</code> belum mengembalikan
              daftar dokumen. Statistik agregat di sebelah kiri berasal dari
              <code> /api/manifest</code> standar.
            </div>
          )}

          {filtered.map((d) => {
            const flag = currencyFromStatus(d.currency_status, d.year);
            const selectedRow = selected === d.doc_id;
            return (
              <button
                key={d.doc_id}
                onClick={() => setSelected(d.doc_id)}
                className="guideline-row"
                style={{
                  width: "100%",
                  padding: "14px 20px",
                  background: selectedRow ? "var(--paper-3)" : "transparent",
                  border: "none",
                  borderBottom: "1px solid var(--rule)",
                  borderLeft: selectedRow
                    ? "2px solid var(--navy)"
                    : "2px solid transparent",
                  cursor: "pointer",
                  textAlign: "left",
                  fontFamily: "var(--font-body-stack)",
                  color: "var(--ink)",
                }}
              >
                <div style={{ minWidth: 0 }}>
                  <div
                    style={{
                      fontSize: 13.5,
                      color: "var(--ink)",
                      fontWeight: 500,
                      overflow: "hidden",
                      textOverflow: "ellipsis",
                      whiteSpace: "nowrap",
                    }}
                  >
                    {d.title}
                  </div>
                  <div
                    className="mono"
                    style={{ fontSize: 10.5, color: "var(--ink-3)", marginTop: 2, overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}
                  >
                    {d.doc_id} · {SOURCE_LABEL[d.source_type] ?? d.source_type} · {d.year}
                  </div>
                </div>
                <div className="mono guideline-list-cell-sm" style={{ fontSize: 11, color: "var(--ink-2)" }}>
                  {SOURCE_LABEL[d.source_type] ?? d.source_type}
                </div>
                <div className="mono guideline-list-cell-sm" style={{ fontSize: 11.5, color: "var(--ink-2)" }}>
                  {d.year}
                </div>
                <div>
                  <CurrencyChip kind={flag} />
                </div>
              </button>
            );
          })}
        </div>

        {/* Detail */}
        <aside
          className="guideline-detail scroll-civic"
          style={{
            flexShrink: 0,
            background: "var(--paper)",
            overflowY: "auto",
          }}
        >
          {selectedDoc ? (
            <DocumentDetail
              doc={selectedDoc}
              onAsk={() => askAbout(selectedDoc.doc_id)}
              onOpen={() => setPdfDoc(selectedDoc.doc_id)}
            />
          ) : (
            <div
              style={{
                padding: 28,
                color: "var(--ink-3)",
                fontSize: 13.5,
                lineHeight: 1.55,
              }}
            >
              Pilih dokumen di tengah untuk melihat metadata, daftar isi, dan
              pintasan &ldquo;Tanya Anamnesa&rdquo;.
            </div>
          )}
        </aside>
      </div>
      <PdfViewer
        docId={pdfDoc}
        page={1}
        onClose={() => setPdfDoc(null)}
      />
    </>
  );
}

function FilterRow({
  label,
  count,
  active,
  onClick,
  dot,
}: {
  label: string;
  count: number;
  active?: boolean;
  onClick: () => void;
  dot?: string;
}) {
  return (
    <button
      type="button"
      onClick={onClick}
      style={{
        display: "flex",
        alignItems: "center",
        gap: 8,
        width: "100%",
        padding: "6px 8px",
        background: active ? "var(--paper)" : "transparent",
        border: "1px solid " + (active ? "var(--rule)" : "transparent"),
        color: active ? "var(--ink)" : "var(--ink-2)",
        fontSize: 12.5,
        fontFamily: "var(--font-body-stack)",
        cursor: "pointer",
        borderRadius: 2,
        textAlign: "left",
      }}
    >
      {dot && <span style={{ width: 7, height: 7, background: dot, borderRadius: "50%" }} />}
      <span style={{ flex: 1 }}>{label}</span>
      <span className="mono" style={{ fontSize: 10.5, color: "var(--ink-3)" }}>
        {count}
      </span>
    </button>
  );
}

function DocumentDetail({
  doc,
  onAsk,
  onOpen,
}: {
  doc: DocumentLite;
  onAsk: () => void;
  onOpen: () => void;
}) {
  const flag = currencyFromStatus(doc.currency_status, doc.year);
  const fav = useFavorites();
  const starred = fav.isFav("doc", doc.doc_id);
  return (
    <div>
      <div style={{ padding: "20px 22px", borderBottom: "1px solid var(--rule)" }}>
        <div style={{ display: "flex", gap: 8, alignItems: "center", marginBottom: 10 }}>
          <span
            className="mono"
            style={{
              fontSize: 10,
              padding: "2px 6px",
              background: "var(--navy)",
              color: "var(--paper)",
              letterSpacing: "0.06em",
            }}
          >
            {(SOURCE_LABEL[doc.source_type] ?? doc.source_type).toUpperCase()}
          </span>
          <CurrencyChip kind={flag} year={doc.year} />
        </div>
        <h3
          className="display"
          style={{
            fontSize: 22,
            margin: 0,
            fontWeight: 500,
            letterSpacing: "-0.01em",
            lineHeight: 1.2,
            color: "var(--ink)",
          }}
        >
          {doc.title}
        </h3>
        <div
          className="mono"
          style={{ fontSize: 11, color: "var(--ink-3)", marginTop: 8, wordBreak: "break-all" }}
        >
          {doc.doc_id}
        </div>

        <div style={{ display: "flex", gap: 6, marginTop: 16, flexWrap: "wrap" }}>
          <button
            type="button"
            onClick={onAsk}
            className="btn btn-primary"
            style={{ padding: "7px 12px", fontSize: 12, flex: 1, justifyContent: "center", minWidth: 160 }}
          >
            Tanya Anamnesa →
          </button>
          <a
            href={`${API_BASE.replace(/\/$/, "")}/api/guideline/${doc.doc_id}.html`}
            target="_blank"
            rel="noreferrer"
            className="btn btn-ghost"
            style={{ padding: "7px 12px", fontSize: 12, textDecoration: "none" }}
            title="Buka versi HTML (ramah mobile, tanpa PDF)"
          >
            Baca di browser ↗
          </a>
          <a
            href={`${API_BASE.replace(/\/$/, "")}/api/guideline/${doc.doc_id}.md`}
            className="btn btn-ghost"
            style={{ padding: "7px 12px", fontSize: 12, textDecoration: "none" }}
            title="Unduh sebagai Markdown (bisa dibaca offline)"
          >
            Unduh .md
          </a>
          <button
            type="button"
            onClick={onOpen}
            className="btn btn-ghost"
            style={{ padding: "7px 12px", fontSize: 12 }}
          >
            Buka PDF ↗
          </button>
          <button
            type="button"
            onClick={() =>
              fav.toggleDoc({
                doc_id: doc.doc_id,
                title: doc.title,
                source_type: doc.source_type,
                year: doc.year,
                currency_status: doc.currency_status,
              })
            }
            className="btn btn-ghost"
            style={{
              padding: "7px 10px",
              fontSize: 12,
              color: starred ? "var(--aging)" : "var(--ink-2)",
            }}
            title={starred ? "Hapus dari Favorit" : "Simpan ke Favorit"}
            aria-pressed={starred}
          >
            {starred ? "★ Tersimpan" : "☆ Simpan"}
          </button>
        </div>
      </div>

      <div style={{ padding: "16px 22px" }}>
        <div className="label" style={{ marginBottom: 10 }}>
          Metadata
        </div>
        <MetaRow k="ID dokumen" v={doc.doc_id} />
        <MetaRow k="Jenis" v={SOURCE_LABEL[doc.source_type] ?? doc.source_type} />
        <MetaRow k="Tahun" v={String(doc.year)} />
        <MetaRow
          k="Status masa berlaku"
          v={
            flag === "current"
              ? "Berlaku"
              : flag === "aging"
                ? "Perlu tinjau (>5 thn)"
                : flag === "superseded"
                  ? "Sudah diganti"
                  : "Dicabut"
          }
        />
      </div>
    </div>
  );
}

function MetaRow({ k, v }: { k: string; v: string }) {
  return (
    <div
      style={{
        display: "flex",
        justifyContent: "space-between",
        gap: 12,
        padding: "4px 0",
        fontSize: 12,
      }}
    >
      <span style={{ color: "var(--ink-3)" }}>{k}</span>
      <span
        className="mono"
        style={{ color: "var(--ink)", textAlign: "right", fontSize: 11, wordBreak: "break-all" }}
      >
        {v}
      </span>
    </div>
  );
}
