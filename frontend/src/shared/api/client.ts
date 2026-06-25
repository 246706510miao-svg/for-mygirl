import type { ApiResponse, AuthResult, IdentityContext, Role } from "../types/api";

const API_BASE_URL = (import.meta.env.VITE_API_BASE_URL || defaultApiBaseUrl()).replace(/\/$/, "");
const SUCCESS_CODES = new Set(["OK", "CREATED"]);
export type ClientRole = "user" | "partner" | "ops";
const LEGACY_AUTH_TOKEN_KEY = "for-mygirl.authToken";

clearLegacyStoredToken();

// 这个函数生成未显式配置时的 API 地址：开发走 Vite 代理，静态包按当前主机推导后端端口。
function defaultApiBaseUrl() {
  if (import.meta.env.DEV || typeof window === "undefined") {
    return "";
  }
  return `${window.location.protocol}//${window.location.hostname}:8080`;
}

export class ApiRequestError extends Error {
  readonly code: string;
  readonly requestId: string;
  readonly status: number;
  readonly details: unknown;

  constructor(message: string, code: string, requestId: string, status: number, details: unknown) {
    super(message);
    this.name = "ApiRequestError";
    this.code = code;
    this.requestId = requestId;
    this.status = status;
    this.details = details;
  }
}

// 这个函数清掉旧版本保存在 localStorage 里的明文 token。
function clearLegacyStoredToken() {
  try {
    if (typeof localStorage !== "undefined") {
      localStorage.removeItem(LEGACY_AUTH_TOKEN_KEY);
    }
  } catch {
    // 某些隐私模式可能禁止 localStorage，忽略即可。
  }
}

// 这个函数生成前端幂等 ID。
export function newClientId(prefix: string) {
  const random = typeof crypto !== "undefined" && "randomUUID" in crypto
    ? crypto.randomUUID().replace(/-/g, "").slice(0, 16)
    : `${Date.now().toString(36)}${Math.random().toString(36).slice(2, 10)}`;
  return `${prefix}_${random}`;
}

// 这个函数生成前端请求追踪 ID。
export function newRequestId() {
  return newClientId("req");
}

// 这个函数拼接 API 地址，未配置 base URL 时使用当前前端源的相对路径。
function apiUrl(path: string) {
  return `${API_BASE_URL}${path}`;
}

// 这个函数解析后端统一响应，兼容空响应和非 JSON 错误页。
async function parsePayload<T>(response: Response): Promise<ApiResponse<T> | null> {
  const text = await response.text();
  if (!text) {
    return null;
  }
  try {
    return JSON.parse(text) as ApiResponse<T>;
  } catch {
    return {
      code: response.ok ? "INVALID_RESPONSE" : `HTTP_${response.status}`,
      message: text,
      data: null,
      requestId: response.headers.get("X-Request-Id") || ""
    };
  }
}

// 这个函数从后端角色推断前端工作区。
function roleFromAuth(role: Role): ClientRole {
  if (role === "OPS_ADMIN" || role === "ADMIN") {
    return "ops";
  }
  return "user";
}

// 这个函数从认证结果推断前端工作区。
function roleFromResult(auth: AuthResult): ClientRole {
  if (auth.person.role === "OPS_ADMIN" || auth.person.role === "ADMIN") {
    return "ops";
  }
  return "user";
}

// 这个函数封装后端统一响应和错误处理，浏览器登录态由 HttpOnly Cookie 自动携带。
export async function apiRequest<T>(path: string, options: RequestInit & { role?: ClientRole; skipAuth?: boolean } = {}): Promise<T> {
  const headers = new Headers(options.headers);
  headers.set("Accept", "application/json");
  if (options.body && !(options.body instanceof FormData) && !headers.has("Content-Type")) {
    headers.set("Content-Type", "application/json");
  }
  headers.set("X-Request-Id", newRequestId());
  const response = await fetch(apiUrl(path), { ...options, credentials: "include", headers });
  const payload = await parsePayload<T>(response);
  if (!payload) {
    throw new ApiRequestError(response.statusText || "后端响应为空", `HTTP_${response.status}`, "", response.status, null);
  }
  if (!response.ok || !SUCCESS_CODES.has(payload.code)) {
    throw new ApiRequestError(payload.message || `HTTP ${response.status}`, payload.code, payload.requestId, response.status, payload.data);
  }
  return payload.data as T;
}

// 这个函数按登录表单账号登录，后端会写入 HttpOnly Cookie。
export async function loginWithCredentials(loginName: string, password: string) {
  const normalized = loginName.trim().toLowerCase();
  const result = await apiRequest<AuthResult>("/api/auth/login", {
    method: "POST",
    skipAuth: true,
    body: JSON.stringify({ loginName: normalized, password })
  });
  const role = roleFromResult(result);
  return { role, auth: result };
}

// 这个函数注册普通用户并由后端写入 HttpOnly Cookie。
export async function registerWithCredentials(loginName: string, displayName: string, password: string) {
  const result = await apiRequest<AuthResult>("/api/auth/register", {
    method: "POST",
    skipAuth: true,
    body: JSON.stringify({ loginName: loginName.trim().toLowerCase(), displayName: displayName.trim(), password })
  });
  const role = roleFromResult(result);
  return { role, auth: result };
}

// 这个函数用浏览器 Cookie 恢复登录状态。
export async function restoreSession() {
  try {
    const context = await apiRequest<IdentityContext>("/api/auth/me");
    return { role: roleFromAuth(context.person.role), context };
  } catch {
    return null;
  }
}

// 这个函数退出当前登录会话。
export async function logoutCurrentSession() {
  try {
    await apiRequest<Record<string, unknown>>("/api/auth/logout", { method: "POST" });
  } catch {
    // 退出时即使 Cookie 已过期，前端也应回到登录页。
  }
}
