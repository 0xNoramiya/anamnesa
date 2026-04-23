"use client";

import { TopBar } from "@/components/shell/TopBar";
import { DrugLookup } from "@/components/app/DrugLookup";
import { useI18n } from "@/components/shell/LanguageProvider";

export default function ObatPage() {
  const { t } = useI18n();
  return (
    <>
      <TopBar title={t("topbar.obat.title")} subtitle={`// ${t("topbar.obat.sub")}`} />
      <DrugLookup />
    </>
  );
}
