"use client";

import { useCallback, useState } from "react";
import { TopBar } from "@/components/shell/TopBar";
import { FastSearch } from "@/components/FastSearch";
import { PdfViewer } from "@/components/PdfViewer";
import { useRouter } from "next/navigation";
import { useI18n } from "@/components/shell/LanguageProvider";

interface PdfOpen { docId: string; page: number }

export default function PencarianPage() {
  const router = useRouter();
  const { t } = useI18n();
  const [pdf, setPdf] = useState<PdfOpen | null>(null);
  const openPdf = useCallback(
    (docId: string, page: number) => setPdf({ docId, page }),
    [],
  );
  const closePdf = useCallback(() => setPdf(null), []);

  const escalate = useCallback(
    (q: string) => {
      // Stash the query in sessionStorage so /chat can pick it up
      // on mount and auto-submit.
      try {
        window.sessionStorage.setItem("anamnesa.prefill_query", q);
      } catch {
        // ignore quota / private mode
      }
      router.push("/chat");
    },
    [router],
  );

  return (
    <>
      <TopBar
        title={t("topbar.search.title")}
        subtitle={`// ${t("topbar.search.sub")}`}
      />
      <div className="mx-auto max-w-[1100px] px-6 lg:px-10 py-6 md:py-8">
        <FastSearch onOpenPdf={openPdf} onEscalate={escalate} />
      </div>
      <PdfViewer
        docId={pdf?.docId ?? null}
        page={pdf?.page ?? 1}
        onClose={closePdf}
      />
    </>
  );
}
