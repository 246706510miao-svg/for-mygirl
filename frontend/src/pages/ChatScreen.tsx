import { useEffect, useRef, type FormEvent } from "react";
import { X } from "lucide-react";
import { GlassScreen } from "../components/layout/GlassScreen";
import { MobileAppShell } from "../components/layout/MobileAppShell";
import type { MobileTabItem } from "../components/layout/MobileAppShell";
import { ScreenHeader } from "../components/layout/ScreenHeader";
import { ChatBubble } from "../components/chat/ChatBubble";
import { Composer } from "../components/chat/Composer";
import { DraftPanel } from "../components/chat/DraftPanel";
import { FeishuTablePanel } from "../components/chat/FeishuTablePanel";
import { ThirdConfirmationPanel } from "../components/chat/ThirdConfirmationPanel";
import { Pressable } from "../components/ui/Pressable";
import type { FeishuAccount, FeishuTableConfig, PendingThirdConfirmation, RecordDraft, ThirdInteractionResponse } from "../shared/types/api";
import type { SaveFeishuAccountPayload, SaveFeishuTablePayload } from "../features/feishu/api";
import { shouldShowInteractionPrompt, type ChatMessageItem } from "../app/chatConversation";

interface ChatScreenProps {
  messages: ChatMessageItem[];
  input: string;
  draft: RecordDraft | null;
  pendingConfirmation: PendingThirdConfirmation | null;
  feishuAccount: FeishuAccount | null;
  feishuTables: FeishuTableConfig[];
  selectedFeishuTableId: string | null;
  feishuLocked: boolean;
  hasSession: boolean;
  tabs: MobileTabItem[];
  busy: boolean;
  onBack: () => void;
  onInputChange: (value: string) => void;
  onSend: (event: FormEvent) => void;
  onConfirmDraft: () => void;
  onRespondConfirmation: (response: ThirdInteractionResponse, content?: string) => void;
  onEditDraft: () => void;
  onVoice: () => void;
  onCancelSession: () => void;
  onSelectFeishuTable: (tableId: string) => void;
  onSaveFeishuAccount: (payload: SaveFeishuAccountPayload) => Promise<boolean | void>;
  onCreateFeishuTable: (payload: SaveFeishuTablePayload) => Promise<boolean | void>;
  onUpdateFeishuTable: (tableId: string, payload: SaveFeishuTablePayload) => Promise<boolean | void>;
  onSetDefaultFeishuTable: (tableId: string) => Promise<boolean | void>;
  onTestFeishuTable: (tableId: string) => Promise<boolean | void>;
}

function composerPlaceholder(confirmation: PendingThirdConfirmation | null) {
  if (confirmation?.interactionKind === "confirm") {
    return "需要调整就直接告诉我";
  }
  if (confirmation?.interactionKind === "choose_candidate") {
    return "直接告诉我你的选择";
  }
  if (confirmation) {
    return "直接回答我";
  }
  return "写下今天的记录";
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
  hasSession,
  tabs,
  busy,
  onBack,
  onInputChange,
  onSend,
  onConfirmDraft,
  onRespondConfirmation,
  onEditDraft,
  onVoice,
  onCancelSession,
  onSelectFeishuTable,
  onSaveFeishuAccount,
  onCreateFeishuTable,
  onUpdateFeishuTable,
  onSetDefaultFeishuTable,
  onTestFeishuTable
}: ChatScreenProps) {
  const conversationEndRef = useRef<HTMLDivElement>(null);
  const interactionPrompt = pendingConfirmation?.requestText?.trim();
  const showInteractionPrompt = shouldShowInteractionPrompt(messages, interactionPrompt);
  const needsExplicitConfirmation = pendingConfirmation?.interactionKind === "confirm";

  useEffect(() => {
    conversationEndRef.current?.scrollIntoView({ behavior: "smooth", block: "nearest" });
  }, [messages.length, interactionPrompt, needsExplicitConfirmation]);

  return (
    <MobileAppShell activeTab="chat" tabs={tabs}>
      <GlassScreen className="chat-screen">
        <ScreenHeader
          title="记录今天"
          subtitle="CCC 正在这里陪你整理"
          onBack={onBack}
          rightSlot={hasSession ? (
            <Pressable className="icon-button" disabled={busy} onClick={onCancelSession} aria-label="取消本次记录">
              <X size={19} />
            </Pressable>
          ) : undefined}
        />
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
          {messages.length === 0 && (
            <div className="chat-welcome">
              <span>CCC</span>
              <h2>今天有什么想留下来的？</h2>
              <p>开心的小事、没说完的话，或者只是有点累，都可以慢慢告诉我。</p>
            </div>
          )}
          {messages.map((message) => (
            <ChatBubble key={message.id} type={message.type} pending={message.pending} error={message.error}>
              {message.content}
            </ChatBubble>
          ))}
          {showInteractionPrompt && (
            <ChatBubble key={`interaction-${pendingConfirmation?.confirmationId}`} type="ai">
              {interactionPrompt}
            </ChatBubble>
          )}
          {pendingConfirmation && needsExplicitConfirmation && <ThirdConfirmationPanel confirmation={pendingConfirmation} busy={busy} onRespond={onRespondConfirmation} />}
          <div ref={conversationEndRef} className="chat-history__end" aria-hidden="true" />
        </section>
        {draft && !pendingConfirmation && <DraftPanel draft={draft} busy={busy} onConfirm={onConfirmDraft} onEdit={onEditDraft} />}
        <Composer value={input} busy={busy} placeholder={composerPlaceholder(pendingConfirmation)} onChange={onInputChange} onSubmit={onSend} onVoice={onVoice} />
      </GlassScreen>
    </MobileAppShell>
  );
}
