import type { FormEvent } from "react";
import { GlassScreen } from "../components/layout/GlassScreen";
import { MobileAppShell } from "../components/layout/MobileAppShell";
import { ScreenHeader } from "../components/layout/ScreenHeader";
import { ChatBubble } from "../components/chat/ChatBubble";
import { Composer } from "../components/chat/Composer";
import { DraftPanel } from "../components/chat/DraftPanel";
import { ThirdConfirmationPanel } from "../components/chat/ThirdConfirmationPanel";
import { EmptyState } from "../components/ui/EmptyState";
import type { PendingThirdConfirmation, RecordDraft } from "../shared/types/api";

interface ChatScreenProps {
  messages: string[];
  input: string;
  draft: RecordDraft | null;
  pendingConfirmation: PendingThirdConfirmation | null;
  busy: boolean;
  onBack: () => void;
  onInputChange: (value: string) => void;
  onSend: (event: FormEvent) => void;
  onConfirmDraft: () => void;
  onApproveConfirmation: () => void;
  onRejectConfirmation: () => void;
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
export function ChatScreen({
  messages,
  input,
  draft,
  pendingConfirmation,
  busy,
  onBack,
  onInputChange,
  onSend,
  onConfirmDraft,
  onApproveConfirmation,
  onRejectConfirmation,
  onEditDraft,
  onVoice
}: ChatScreenProps) {
  const composerBusy = busy || Boolean(pendingConfirmation);

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
        {pendingConfirmation && <ThirdConfirmationPanel confirmation={pendingConfirmation} busy={busy} onApprove={onApproveConfirmation} onReject={onRejectConfirmation} />}
        {draft && !pendingConfirmation && <DraftPanel draft={draft} busy={busy} onConfirm={onConfirmDraft} onEdit={onEditDraft} />}
        <Composer value={input} busy={composerBusy} onChange={onInputChange} onSubmit={onSend} onVoice={onVoice} />
      </GlassScreen>
    </MobileAppShell>
  );
}
