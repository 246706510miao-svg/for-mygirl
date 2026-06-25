import { apiRequest, type ClientRole } from "../../shared/api/client";
import type { FeishuAccount, FeishuTableConfig, FeishuTableList, FeishuTableTestResult } from "../../shared/types/api";

export interface SaveFeishuAccountPayload {
  enabled: boolean;
  appId: string;
  appSecret?: string;
  tenantAccessToken?: string;
  userIdType: string;
}

export interface SaveFeishuTablePayload {
  displayName: string;
  tableUrl: string;
  enabled: boolean;
  fieldNameMap?: Record<string, unknown>;
}

export function fetchFeishuAccount(role: ClientRole) {
  return apiRequest<FeishuAccount>("/api/user/feishu/account", { role });
}

export function saveFeishuAccount(role: ClientRole, payload: SaveFeishuAccountPayload) {
  return apiRequest<FeishuAccount>("/api/user/feishu/account", {
    method: "PUT",
    role,
    body: JSON.stringify(payload)
  });
}

export async function fetchFeishuTables(role: ClientRole) {
  const result = await apiRequest<FeishuTableList>("/api/user/feishu/tables", { role });
  return result.items;
}

export function createFeishuTable(role: ClientRole, payload: SaveFeishuTablePayload) {
  return apiRequest<FeishuTableConfig>("/api/user/feishu/tables", {
    method: "POST",
    role,
    body: JSON.stringify(payload)
  });
}

export function updateFeishuTable(role: ClientRole, tableId: string, payload: SaveFeishuTablePayload) {
  return apiRequest<FeishuTableConfig>(`/api/user/feishu/tables/${tableId}`, {
    method: "PATCH",
    role,
    body: JSON.stringify(payload)
  });
}

export function setDefaultFeishuTable(role: ClientRole, tableId: string) {
  return apiRequest<FeishuTableConfig>(`/api/user/feishu/tables/${tableId}/default`, {
    method: "POST",
    role
  });
}

export function testFeishuTable(role: ClientRole, tableId: string) {
  return apiRequest<FeishuTableTestResult>(`/api/user/feishu/tables/${tableId}/test`, {
    method: "POST",
    role
  });
}
