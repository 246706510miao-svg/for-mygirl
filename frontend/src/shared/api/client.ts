import type { ApiResponse, AuthResult } from "../types/api";

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || "http://localhost:8080";
export type ClientRole = "user" | "partner" | "ops";

const tokens: Record<ClientRole, string> = {
  user: "",
  partner: "",
  ops: ""
};

// 这个函数生成前端请求追踪 ID。
export function newRequestId() {
  return `req_${crypto.randomUUID().replace(/-/g, "").slice(0, 16)}`;
}

// 这个函数保存指定角色的开发 token。
export function setToken(role: ClientRole, token: string) {
  tokens[role] = token;
}

// 这个函数读取指定角色的开发 token。
export function getToken(role: ClientRole) {
  return tokens[role] || "";
}

// 这个函数封装后端统一响应和错误处理。
export async function apiRequest<T>(path: string, options: RequestInit & { role?: ClientRole } = {}): Promise<T> {
  const headers = new Headers(options.headers);
  headers.set("Content-Type", "application/json");
  headers.set("X-Request-Id", newRequestId());
  const token = options.role ? getToken(options.role) : "";
  if (token) {
    headers.set("Authorization", `Bearer ${token}`);
  }
  const response = await fetch(`${API_BASE_URL}${path}`, { ...options, headers });
  const payload = (await response.json()) as ApiResponse<T>;
  if (!response.ok || payload.code === "INTERNAL_ERROR") {
    throw new Error(payload.message || `HTTP ${response.status}`);
  }
  return payload.data;
}

// 这个函数按开发角色使用固定账号登录并缓存 token。
export async function login(role: ClientRole) {
  const loginName = role === "ops" ? "admin" : role;
  const result = await apiRequest<AuthResult>("/api/auth/login", {
    method: "POST",
    body: JSON.stringify({ loginName, password: "dev" })
  });
  setToken(role, result.accessToken);
  return result;
}

// 这个函数按登录表单账号登录并缓存 token。
export async function loginWithCredentials(loginName: string, password: string) {
  const normalized = loginName.trim().toLowerCase();
  const role: ClientRole = normalized === "admin" ? "ops" : normalized === "partner" || normalized === "ta" ? "partner" : "user";
  const result = await apiRequest<AuthResult>("/api/auth/login", {
    method: "POST",
    body: JSON.stringify({ loginName: normalized || "user", password })
  });
  setToken(role, result.accessToken);
  return { role, auth: result };
}
