import { apiRequest, login, newClientId, type ClientRole } from "../../shared/api/client";
import type { PageResult, RecordDisplay, RecordSession, SendMessageResult, UserHome } from "../../shared/types/api";

// 这个函数初始化记录模块需要的用户 token。
export function loginRecordUser() {
  return login("user");
}

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
export function createRecordSession(role: ClientRole, recordDate: string) {
  return apiRequest<RecordSession>("/api/record-sessions", {
    method: "POST",
    role,
    body: JSON.stringify({ recordDate, source: "user_home" })
  });
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
  return apiRequest<Record<string, unknown>>(`/api/record-sessions/${sessionId}/confirm`, {
    method: "POST",
    role,
    body: JSON.stringify({ clientConfirmId: newClientId("cfid"), draftId })
  });
}
