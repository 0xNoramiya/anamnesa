import { TopBar } from "@/components/shell/TopBar";
import { ChatMode } from "@/components/app/ChatMode";

export const metadata = { title: "Chat · Anamnesa" };

export default function ChatPage() {
  return (
    <>
      <TopBar title="Mode Agen" subtitle="// agentic RAG · dengan sitasi halaman" />
      <ChatMode />
    </>
  );
}
