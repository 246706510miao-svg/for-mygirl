import { apiRequest, newClientId, type ClientRole } from "../../shared/api/client";
import type { ConfirmRecordResult, NewsFocus, PageResult, PendingThirdConfirmation, RecordDisplay, RecordSession, RecordSessionDetail, SendMessageResult, ThirdInteractionResponse, UserHome } from "../../shared/types/api";
import { buildResumeRecordConfirmRequest } from "./interactionRequest";

// 这个函数读取用户首页和最近记录。
export async function fetchRecordHome(role: ClientRole) {
  const home = await apiRequest<UserHome>("/api/user/home", { role });
  const records = await fetchRecentRecords(role);
  return { home, records };
}

// 这个函数读取当前用户最近记录。
export async function fetchRecentRecords(role: ClientRole) {
  const records = await apiRequest<PageResult<RecordDisplay>>("/api/records/recent?page=1&pageSize=20", { role });
  return records.items;
}

// 这个函数读取绑定用户最近记录。
export async function fetchBoundUserRecentRecords(role: ClientRole) {
  const records = await apiRequest<PageResult<RecordDisplay>>("/api/bound-user/records/recent?page=1&pageSize=20", { role });
  return records.items;
}

// 这个函数创建新的记录会话。
export function createRecordSession(role: ClientRole, recordDate: string, feishuTableConfigId?: string | null) {
  return apiRequest<RecordSession>("/api/record-sessions", {
    method: "POST",
    role,
    body: JSON.stringify({ recordDate, source: "user_home", feishuTableConfigId })
  });
}

// 这个函数读取共享每日热门的当天或昨天结果。
export function fetchNewsFocus(role: ClientRole, date: string) {
  return apiRequest<NewsFocus>(`/api/user/news-focus?date=${encodeURIComponent(date)}`, { role });
}

// 这个函数读取记录会话详情，包含 third workflow 最新处理状态。
export function fetchRecordSession(role: ClientRole, sessionId: string) {
  return apiRequest<RecordSessionDetail>(`/api/record-sessions/${sessionId}`, { role });
}

// 这个函数发送文本消息并生成草稿。
export function sendRecordMessage(role: ClientRole, sessionId: string, content: string) {
  return apiRequest<SendMessageResult>(`/api/record-sessions/${sessionId}/messages`, {
    method: "POST",
    role,
    body: JSON.stringify({ clientMessageId: newClientId("cmid"), content })
  });
}

// 这个函数确认当前草稿写入。
export function confirmRecordDraft(role: ClientRole, sessionId: string, draftId: string) {
  return apiRequest<ConfirmRecordResult>(`/api/record-sessions/${sessionId}/confirm`, {
    method: "POST",
    role,
    body: JSON.stringify({ clientConfirmId: newClientId("cfid"), draftId })
  });
}

// 这个函数回答或处理 third 当前等待中的交互。
export function resumeRecordConfirm(role: ClientRole, sessionId: string, confirmation: PendingThirdConfirmation, response: ThirdInteractionResponse, content = "") {
  const request = buildResumeRecordConfirmRequest(sessionId, confirmation, response, content);
  return apiRequest<ConfirmRecordResult>(request.path, { ...request.options, role });
}

// 这个函数取消当前尚未完成的记录会话。
export function cancelRecordSession(role: ClientRole, sessionId: string) {
  return apiRequest<RecordSession>(`/api/record-sessions/${sessionId}/cancel`, {
    method: "POST",
    role
  });
}
