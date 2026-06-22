import type { FormEvent } from "react";
import { GlassScreen } from "../components/layout/GlassScreen";
import { MobileAppShell } from "../components/layout/MobileAppShell";
import { ScreenHeader } from "../components/layout/ScreenHeader";
import { ChatBubble } from "../components/chat/ChatBubble";
import { Composer } from "../components/chat/Composer";
import { DraftPanel } from "../components/chat/DraftPanel";
import { EmptyState } from "../components/ui/EmptyState";
import type { RecordDraft } from "../shared/types/api";

interface ChatScreenProps {
  messages: string[];
  input: string;
  draft: RecordDraft | null;
  busy: boolean;
  onBack: () => void;
  onInputChange: (value: string) => void;
  onSend: (event: FormEvent) => void;
  onConfirmDraft: () => void;
  onEditDraft: () => void;
  onVoice: () => void;
}

function messageType(item: string) {
  if (item.startsWith("我：")) {
    return "user" as const;
  }
  if (item.startsWith("系统：")) {
    return "system" as const;
  }
  return "ai" as const;
}

// 这个页面承载记录对话、草稿和确认写入。
export function ChatScreen({ messages, input, draft, busy, onBack, onInputChange, onSend, onConfirmDraft, onEditDraft, onVoice }: ChatScreenProps) {
  return (
    <MobileAppShell>
      <GlassScreen className="chat-screen">
        <ScreenHeader title="Chat" onBack={onBack} />
        <section className="chat-history">
          {messages.length === 0 && <EmptyState title="暂无对话" description="写下今天发生的小事。" />}
          {messages.map((item, index) => (
            <ChatBubble key={`${item}-${index}`} type={messageType(item)}>
              {item}
            </ChatBubble>
          ))}
        </section>
        {draft && <DraftPanel draft={draft} busy={busy} onConfirm={onConfirmDraft} onEdit={onEditDraft} />}
        <Composer value={input} busy={busy} onChange={onInputChange} onSubmit={onSend} onVoice={onVoice} />
      </GlassScreen>
    </MobileAppShell>
  );
}
