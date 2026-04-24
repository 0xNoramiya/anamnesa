import type { FinalResponse } from "./types";
import { REFUSAL_MESSAGES_ID } from "./refusalMessages";

/**
 * Format a FinalResponse as Bahasa-friendly Markdown suitable for pasting
 * into shift notes or exporting as a .md file.
 *
 * Conventions:
 *  - Inline `[[doc:page:slug]]` citations become `[^N]` numeric footnotes.
 *  - A "Referensi" section lists the mapped citations with doc/page/year
 *    and (when present) a short chunk-text quote as `>` block.
 *  - Currency flags (aging / superseded / withdrawn) surface next to the
 *    reference so the exported note carries the same caveat the UI does.
 *  - Refusals get a dedicated "Penolakan" section plus, when populated,
 *    the retrieval_preview near-misses.
 *  - A short disclaimer footer closes every export — the reader should
 *    see the provenance / not-a-medical-device context even in plain text.
 */
export function buildAnswerMarkdown(query: string, final: FinalResponse): string {
  const lines: string[] = [];
  lines.push(`# Pertanyaan`, "", query.trim(), "");

  if (final.refusal_reason) {
    const msg = REFUSAL_MESSAGES_ID[final.refusal_reason] ?? final.answer_markdown;
    lines.push(`# Penolakan`, "", msg.trim(), "");
    lines.push(
      `> Alasan: \`${final.refusal_reason}\``,
      "",
    );
    const hints = final.retrieval_preview ?? [];
    if (hints.length > 0) {
      lines.push(`## Dokumen yang ditemukan (tidak sesuai)`, "");
      hints.forEach((h, i) => {
        lines.push(
          `${i + 1}. **${h.doc_id}** · hal ${h.page} · ${formatSource(h.source_type)} (${h.year})`,
        );
        if (h.text_preview) {
          lines.push(`   > ${h.text_preview}`);
        }
        lines.push("");
      });
    }
  } else {
    // Build the citation index ourselves (same order as the UI).
    const indexByKey = new Map<string, number>();
    final.citations.forEach((c, i) => indexByKey.set(c.key, i + 1));

    const flagsByKey = new Map<
      string,
      { status: string; source_year: number; superseding_doc_id: string | null }
    >();
    final.currency_flags.forEach((f) => flagsByKey.set(f.citation_key, f));

    // Replace [[key]] with [^N] footnotes. Keep unknown keys as-is with
    // a ~ prefix so the reader can see Anamnesa emitted them.
    const bodyTransformed = final.answer_markdown.replace(
      /\[\[([^\]]+)\]\]/g,
      (full, key: string) => {
        const n = indexByKey.get(key);
        return n ? `[^${n}]` : `[[~${key}]]`;
      },
    );
    lines.push(`# Jawaban`, "", bodyTransformed.trim(), "");

    if (final.citations.length > 0) {
      lines.push(`# Referensi`, "");
      final.citations.forEach((c, i) => {
        const n = i + 1;
        const flag = flagsByKey.get(c.key);
        const currency = flag ? formatCurrency(flag) : "";
        lines.push(
          `[^${n}]: **${c.doc_id}** · hal ${c.page}${currency ? ` · ${currency}` : ""}`,
        );
        const quote = (c.chunk_text ?? "").replace(/\s+/g, " ").trim();
        if (quote) {
          lines.push(`> ${quote.slice(0, 420)}${quote.length > 420 ? "…" : ""}`);
        }
        lines.push("");
      });
    }
  }

  lines.push(`---`, "");
  lines.push(
    `_Anamnesa membantu dokter menemukan dan mengutip pedoman Indonesia yang berlaku. Ini bukan alat diagnosis atau rekomendasi terapi untuk pasien individual. Keputusan klinis tetap menjadi tanggung jawab dokter._`,
    "",
  );
  if (final.from_cache) {
    lines.push(`_Jawaban diambil dari cache · usia ${formatAge(final.cached_age_s ?? null)}._`, "");
  }
  lines.push(`_Diekspor dari https://anamnesa.kudaliar.id pada ${new Date().toISOString()}._`);
  return lines.join("\n");
}

function formatSource(s: string): string {
  return s.replace(/_/g, " ").replace(/\b\w/g, (c) => c.toUpperCase());
}

function formatCurrency(flag: {
  status: string;
  source_year: number;
  superseding_doc_id: string | null;
}): string {
  const label =
    flag.status === "aging"
      ? "⚠ Aging"
      : flag.status === "superseded"
        ? `⚠ Superseded → ${flag.superseding_doc_id ?? "?"}`
        : flag.status === "withdrawn"
          ? "⚠ Withdrawn"
          : flag.status === "current"
            ? "✓ Current"
            : flag.status;
  return `${label} · ${flag.source_year}`;
}

function formatAge(s: number | null): string {
  if (s == null) return "baru saja";
  if (s < 60) return "baru saja";
  if (s < 3600) return `${Math.round(s / 60)} menit`;
  if (s < 86400) return `${Math.round(s / 3600)} jam`;
  return `${Math.round(s / 86400)} hari`;
}

/**
 * Download a string as a file by synthesising an anchor click. Safe in
 * all modern browsers; revokes the object URL after ~5s to release the
 * blob reference.
 */
export function downloadText(
  filename: string,
  contents: string,
  mime: string = "text/markdown;charset=utf-8",
): void {
  const blob = new Blob([contents], { type: mime });
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = filename;
  document.body.appendChild(a);
  a.click();
  a.remove();
  setTimeout(() => URL.revokeObjectURL(url), 5_000);
}

export function suggestedFilename(): string {
  const d = new Date();
  const pad = (n: number) => n.toString().padStart(2, "0");
  const stamp = `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())}-${pad(d.getHours())}${pad(d.getMinutes())}`;
  return `anamnesa-${stamp}.md`;
}

/**
 * Build a plain-text share string tuned for WhatsApp / Telegram, where
 * heavy Markdown falls apart visually. Strips headings, fence markers,
 * and citation-key brackets; replaces inline [[key]] with "[N]" to
 * match the numbered Referensi list. Truncates body + quotes so the
 * share payload stays inside typical message-size comfort (~2-3 KB).
 *
 * Leaves *bold* and _italic_ alone — WhatsApp / Telegram render those.
 */
export function buildShareText(query: string, final: FinalResponse): string {
  const lines: string[] = [];
  lines.push(`*Pedoman:* ${query.trim()}`);
  lines.push("");

  if (final.refusal_reason) {
    const msg = REFUSAL_MESSAGES_ID[final.refusal_reason] ?? final.answer_markdown;
    lines.push(msg.trim());
    lines.push("");
    lines.push(`_Alasan: ${final.refusal_reason}_`);
    lines.push("");
  } else {
    const indexByKey = new Map<string, number>();
    final.citations.forEach((c, i) => indexByKey.set(c.key, i + 1));

    let body = final.answer_markdown
      .replace(/\[\[([^\]]+)\]\]/g, (_full, key: string) => {
        const n = indexByKey.get(key);
        return n ? `[${n}]` : "";
      })
      .replace(/^#{1,6}\s+/gm, "")
      .replace(/\n{3,}/g, "\n\n")
      .trim();

    if (body.length > 1600) {
      body = body.slice(0, 1600).replace(/\s+\S*$/, "") + "…";
    }
    lines.push(body);
    lines.push("");

    if (final.citations.length > 0) {
      lines.push("*Referensi:*");
      final.citations.slice(0, 5).forEach((c, i) => {
        lines.push(`[${i + 1}] ${c.doc_id} · hal ${c.page}`);
      });
      if (final.citations.length > 5) {
        lines.push(`…+${final.citations.length - 5} sitasi lain`);
      }
      lines.push("");
    }
  }

  lines.push("—");
  lines.push("Dari Anamnesa · pencarian pedoman klinis Indonesia");
  lines.push("https://anamnesa.kudaliar.id");
  return lines.join("\n");
}

/**
 * Construct a wa.me deep link that opens WhatsApp with the share text
 * pre-filled. Falls back to Web WhatsApp on desktop when the native app
 * isn't installed.
 */
export function whatsappShareUrl(text: string): string {
  return `https://wa.me/?text=${encodeURIComponent(text)}`;
}
