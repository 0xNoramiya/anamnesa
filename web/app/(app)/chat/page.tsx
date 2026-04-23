"use client";

import { TopBar } from "@/components/shell/TopBar";
import { ChatMode } from "@/components/app/ChatMode";
import { useI18n } from "@/components/shell/LanguageProvider";

export default function ChatPage() {
  const { t } = useI18n();
  return (
    <>
      <TopBar title={t("topbar.chat.title")} subtitle={`// ${t("topbar.chat.sub")}`} />
      <ChatMode />
    </>
  );
}
