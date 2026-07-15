import type { RecordMessage, RecordSessionDetail } from "../shared/types/api";

export type ChatMessageType = "user" | "ai" | "system";

export interface ChatMessageItem {
  id: string;
  type: ChatMessageType;
  content: string;
  pending?: boolean;
  error?: boolean;
}

const GENERIC_INTERACTION_MESSAGES = new Set([
  "还差一点信息，回答后我会继续帮你整理。",
  "我找到几个可能的选项，想请你选一下。",
  "我已经准备好下一步，确认后才会执行。",
  "请确认即将写入飞书的内容。",
  "请补充信息，我会继续准备写入内容。"
]);

function messageType(message: RecordMessage): ChatMessageType {
  if (message.sender === "user") {
    return "user";
  }
  if (message.sender === "system") {
    return "system";
  }
  return "ai";
}

function isProcessing(detail: RecordSessionDetail) {
  return Boolean(detail.latestWorkflowTask && ["submitted", "running"].includes(detail.latestWorkflowTask.status));
}

// 把后端消息变成对话视图；旧版泛化追问不再展示。
export function conversationMessagesFromDetail(detail: RecordSessionDetail): ChatMessageItem[] {
  const messages: ChatMessageItem[] = detail.messages
    .filter((message) => !GENERIC_INTERACTION_MESSAGES.has(message.content.trim()))
    .map((message) => ({
      id: message.id,
      type: messageType(message),
      content: message.content
    }));
  if (isProcessing(detail)) {
    messages.push({
      id: `pending-${detail.latestWorkflowTask?.id || detail.session.id}`,
      type: "ai",
      content: "正在思考…",
      pending: true
    });
  } else if (detail.latestWorkflowTask?.status === "failed" && messages[messages.length - 1]?.content !== "这次没有顺利完成，请再试一次。") {
    messages.push({
      id: `error-${detail.latestWorkflowTask.id}`,
      type: "ai",
      content: "这次没有顺利完成，请再试一次。",
      error: true
    });
  }
  return messages;
}

// 用户点击发送时先把本轮对话放进消息流，不等待网络请求结束。
export function appendOptimisticTurn(messages: ChatMessageItem[], content: string, turnId: string, waitingText = "正在思考…") {
  return [
    ...messages.filter((message) => !message.pending),
    { id: `user-${turnId}`, type: "user" as const, content },
    { id: `pending-${turnId}`, type: "ai" as const, content: waitingText, pending: true }
  ];
}

export function replacePendingWithMessage(messages: ChatMessageItem[], pendingId: string, content: string, type: ChatMessageType = "ai") {
  const expectedId = `pending-${pendingId}`;
  let replaced = false;
  const next = messages.map((message) => {
    if (message.id !== expectedId) {
      return message;
    }
    replaced = true;
    return { id: message.id, type, content };
  });
  if (!replaced) {
    next.push({ id: `reply-${pendingId}`, type, content });
  }
  return next;
}

// 请求失败时用对话内的简短回复替换思考状态，避免展示原始接口异常。
export function replacePendingWithError(messages: ChatMessageItem[], pendingId: string, content: string) {
  const expectedId = `pending-${pendingId}`;
  let replaced = false;
  const next = messages.map((message) => {
    if (message.id !== expectedId) {
      return message;
    }
    replaced = true;
    return { ...message, content, pending: false, error: true };
  });
  if (!replaced) {
    next.push({ id: `error-${pendingId}`, type: "ai", content, error: true });
  }
  return next;
}
