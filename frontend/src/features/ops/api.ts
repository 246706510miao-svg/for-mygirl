import { apiRequest, login } from "../../shared/api/client";

export type OpsRecord = Record<string, unknown>;

// 这个函数初始化后台运维 token。
export function loginOpsUser() {
  return login("ops");
}

// 这个函数读取后台运维首页统计。
export function fetchOpsDashboard() {
  return apiRequest<Record<string, unknown>>("/api/admin/dashboard", { role: "ops" });
}

// 这个函数读取后台运维记录列表。
export async function fetchOpsRecords() {
  const data = await apiRequest<{ items: OpsRecord[] }>("/api/admin/records?page=1&pageSize=20", { role: "ops" });
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
