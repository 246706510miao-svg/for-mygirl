import type { RecordDraft, RecordSession, RecordSessionDetail, PendingThirdConfirmation } from "../shared/types/api";

export interface RecordConversationState {
  session: RecordSession | null;
  draft: RecordDraft | null;
  pendingConfirmation: PendingThirdConfirmation | null;
}

// 后端在确认完成后仍会返回 currentDraft；终态必须优先清空交互状态，避免留下无法再次确认的草稿卡。
export function recordConversationState(detail: RecordSessionDetail): RecordConversationState {
  const terminal = detail.session.status === "confirmed" || detail.session.status === "cancelled" || Boolean(detail.record);
  if (terminal) {
    return {
      session: null,
      draft: null,
      pendingConfirmation: null
    };
  }
  return {
    session: detail.session,
    draft: detail.currentDraft ?? null,
    pendingConfirmation: detail.pendingConfirmation ?? null
  };
}
