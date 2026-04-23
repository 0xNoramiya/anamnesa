"use client";

import { useCallback } from "react";
import { useRouter } from "next/navigation";
import { TopBar } from "@/components/shell/TopBar";
import { HistoryPanel } from "@/components/HistoryPanel";
import { useHistory } from "@/lib/useHistory";
import { useI18n } from "@/components/shell/LanguageProvider";
import type { FinalResponse } from "@/lib/types";

export default function RiwayatPage() {
  const history = useHistory();
  const router = useRouter();
  const { t } = useI18n();

  const loadEntry = useCallback(
    (entry: { query: string; final: FinalResponse }) => {
      // Stash the final in sessionStorage so Chat can restore it without
      // re-running the pipeline. Keep it single-shot.
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
        title={t("topbar.history.title")}
        subtitle={`// ${t("topbar.history.sub")}`}
      />
      <div className="mx-auto max-w-[1100px] px-6 lg:px-10 py-6 md:py-8">
        {history.entries.length === 0 ? (
          <div
            style={{
              padding: "48px 24px",
              textAlign: "center",
              border: "1px dashed var(--rule)",
              background: "var(--paper-2)",
              color: "var(--ink-3)",
              borderRadius: 2,
            }}
          >
            <div className="display" style={{ fontSize: 18, color: "var(--ink)", marginBottom: 8 }}>
              {t("page.history.empty_title")}
            </div>
            <p
              style={{ fontSize: 13.5, lineHeight: 1.55, maxWidth: 360, margin: "0 auto" }}
              dangerouslySetInnerHTML={{ __html: t("page.history.empty_body") }}
            />
          </div>
        ) : (
          <HistoryPanel
            entries={history.entries}
            onPick={loadEntry}
            onClear={history.clearAll}
            onRemove={history.removeEntry}
          />
        )}
      </div>
    </>
  );
}
