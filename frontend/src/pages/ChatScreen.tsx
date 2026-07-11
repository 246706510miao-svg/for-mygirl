import type { FormEvent } from "react";
import { GlassScreen } from "../components/layout/GlassScreen";
import { MobileAppShell } from "../components/layout/MobileAppShell";
import { ScreenHeader } from "../components/layout/ScreenHeader";
import { ChatBubble } from "../components/chat/ChatBubble";
import { Composer } from "../components/chat/Composer";
import { DraftPanel } from "../components/chat/DraftPanel";
import { FeishuTablePanel } from "../components/chat/FeishuTablePanel";
import { ThirdConfirmationPanel } from "../components/chat/ThirdConfirmationPanel";
import { EmptyState } from "../components/ui/EmptyState";
import type { FeishuAccount, FeishuTableConfig, PendingThirdConfirmation, RecordDraft, ThirdInteractionResponse } from "../shared/types/api";
import type { SaveFeishuAccountPayload, SaveFeishuTablePayload } from "../features/feishu/api";

interface ChatScreenProps {
  messages: string[];
  input: string;
  draft: RecordDraft | null;
  pendingConfirmation: PendingThirdConfirmation | null;
  feishuAccount: FeishuAccount | null;
  feishuTables: FeishuTableConfig[];
  selectedFeishuTableId: string | null;
  feishuLocked: boolean;
  busy: boolean;
  onBack: () => void;
  onInputChange: (value: string) => void;
  onSend: (event: FormEvent) => void;
  onConfirmDraft: () => void;
  onRespondConfirmation: (response: ThirdInteractionResponse, content?: string) => void;
  onEditDraft: () => void;
  onVoice: () => void;
  onSelectFeishuTable: (tableId: string) => void;
  onSaveFeishuAccount: (payload: SaveFeishuAccountPayload) => Promise<boolean | void>;
  onCreateFeishuTable: (payload: SaveFeishuTablePayload) => Promise<boolean | void>;
  onUpdateFeishuTable: (tableId: string, payload: SaveFeishuTablePayload) => Promise<boolean | void>;
  onSetDefaultFeishuTable: (tableId: string) => Promise<boolean | void>;
  onTestFeishuTable: (tableId: string) => Promise<boolean | void>;
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
  feishuAccount,
  feishuTables,
  selectedFeishuTableId,
  feishuLocked,
  busy,
  onBack,
  onInputChange,
  onSend,
  onConfirmDraft,
  onRespondConfirmation,
  onEditDraft,
  onVoice,
  onSelectFeishuTable,
  onSaveFeishuAccount,
  onCreateFeishuTable,
  onUpdateFeishuTable,
  onSetDefaultFeishuTable,
  onTestFeishuTable
}: ChatScreenProps) {
  return (
    <MobileAppShell>
      <GlassScreen className="chat-screen">
        <ScreenHeader title="Chat" onBack={onBack} />
        <FeishuTablePanel
          account={feishuAccount}
          tables={feishuTables}
          selectedTableId={selectedFeishuTableId}
          locked={feishuLocked}
          busy={busy}
          onSelectTable={onSelectFeishuTable}
          onSaveAccount={onSaveFeishuAccount}
          onCreateTable={onCreateFeishuTable}
          onUpdateTable={onUpdateFeishuTable}
          onSetDefault={onSetDefaultFeishuTable}
          onTestTable={onTestFeishuTable}
        />
        <section className="chat-history">
          {messages.length === 0 && <EmptyState title="暂无对话" description="写下今天发生的小事。" />}
          {messages.map((item, index) => (
            <ChatBubble key={`${item}-${index}`} type={messageType(item)}>
              {item}
            </ChatBubble>
          ))}
        </section>
        {pendingConfirmation && <ThirdConfirmationPanel confirmation={pendingConfirmation} busy={busy} onRespond={onRespondConfirmation} />}
        {draft && !pendingConfirmation && <DraftPanel draft={draft} busy={busy} onConfirm={onConfirmDraft} onEdit={onEditDraft} />}
        {!pendingConfirmation && <Composer value={input} busy={busy} onChange={onInputChange} onSubmit={onSend} onVoice={onVoice} />}
      </GlassScreen>
    </MobileAppShell>
  );
}
