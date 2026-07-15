import { apiRequest } from "../../shared/api/client";

export type OpsRecord = Record<string, unknown>;

export interface OpsRecordQuery {
  date?: string;
  status?: string;
  onlyAbnormal?: boolean;
  page?: number;
  pageSize?: number;
}

// 这个函数读取后台运维首页统计。
export function fetchOpsDashboard() {
    return apiRequest<Record<string, unknown>>("/api/admin/dashboard", { role: "ops" });
}

// 这个函数读取后台运维记录列表。
export async function fetchOpsRecords(query: OpsRecordQuery = {}) {
  const search = new URLSearchParams({
    page: String(query.page ?? 1),
    pageSize: String(query.pageSize ?? 20)
  });
  if (query.date) search.set("date", query.date);
  if (query.status) search.set("status", query.status);
  if (query.onlyAbnormal) search.set("onlyAbnormal", "true");
  const data = await apiRequest<{ items: OpsRecord[] }>(`/api/admin/records?${search.toString()}`, { role: "ops" });
  return data.items;
}

// 这个函数读取后台运维记录详情。
export function fetchOpsRecordDetail(recordId: string) {
  return apiRequest<Record<string, unknown>>(`/api/admin/records/${recordId}`, { role: "ops" });
}

// 这个函数读取后台运维记录追踪。
export function fetchOpsRecordTrace(recordId: string) {
  return apiRequest<Record<string, unknown>>(`/api/admin/records/${recordId}/trace`, { role: "ops" });
}

// 这个函数读取指定用户与日期的首页内容配置。
export function fetchOpsDailyContents(targetUserId: string, date: string) {
  const search = new URLSearchParams({ targetUserId, date });
  return apiRequest<Record<string, unknown>>(`/api/admin/daily-contents?${search.toString()}`, { role: "ops" });
}

// 这个函数保存指定用户与日期的首页内容配置。
export function saveOpsDailyContents(targetUserId: string, date: string, contents: Record<string, unknown>[]) {
  return apiRequest<Record<string, unknown>>("/api/admin/daily-contents", {
    method: "PUT",
    role: "ops",
    body: JSON.stringify({ targetUserId, date, contents })
  });
}

// 这个函数重试指定记录的飞书同步。
export function retryOpsRecordSync(recordId: string, mode = "reuse_payload") {
  return apiRequest<Record<string, unknown>>(`/api/admin/records/${recordId}/retry-sync`, {
    method: "POST",
    role: "ops",
    body: JSON.stringify({ mode })
  });
}

// 这个函数更新记录在用户端的展示内容。
export function updateOpsRecordDisplay(recordId: string, payload: Record<string, unknown>) {
  return apiRequest<Record<string, unknown>>(`/api/admin/records/${recordId}/display`, {
    method: "PATCH",
    role: "ops",
    body: JSON.stringify(payload)
  });
}

// 这个函数按会话、记录或 third session 聚合追踪信息。
export function fetchOpsTrace(query: { sessionId?: string; recordId?: string; thirdSessionId?: string }) {
  const search = new URLSearchParams();
  if (query.sessionId) search.set("sessionId", query.sessionId);
  if (query.recordId) search.set("recordId", query.recordId);
  if (query.thirdSessionId) search.set("thirdSessionId", query.thirdSessionId);
  return apiRequest<Record<string, unknown>>(`/api/admin/record-traces?${search.toString()}`, { role: "ops" });
}

// 这个函数按记录会话 ID 查询完整追踪。
export function fetchOpsSessionTrace(sessionId: string) {
  return apiRequest<Record<string, unknown>>(`/api/admin/record-sessions/${sessionId}/trace`, { role: "ops" });
}
