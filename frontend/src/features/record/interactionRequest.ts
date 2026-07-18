import type { PendingThirdConfirmation, ThirdInteractionResponse } from "../../shared/types/api";

// 这个函数集中构造 third 当前交互的后端请求，避免 confirmationId 等字段在调用层漂移。
export function buildResumeRecordConfirmRequest(
  sessionId: string,
  confirmation: PendingThirdConfirmation,
  response: ThirdInteractionResponse,
  content = ""
) {
  return {
    path: `/api/record-sessions/${sessionId}/confirm/resume`,
    options: {
      method: "POST",
      body: JSON.stringify({
        clientConfirmId: confirmation.clientConfirmId,
        draftId: confirmation.draftId,
        thirdSessionId: confirmation.thirdSessionId,
        confirmationId: confirmation.confirmationId,
        response,
        content,
        approved: response === "approve"
      })
    }
  };
}
