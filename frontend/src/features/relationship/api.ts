import { apiRequest, type ClientRole } from "../../shared/api/client";
import type { BindingInfo, IdentityContext, ViewRole } from "../../shared/types/api";

// 这个函数读取当前登录人和视角上下文。
export function fetchIdentityContext(role: ClientRole) {
  return apiRequest<IdentityContext>("/api/auth/me", { role });
}

// 这个函数切换用户视角或绑定管理员视角。
export function switchViewRole(role: ClientRole, viewRole: ViewRole) {
  return apiRequest<IdentityContext>("/api/identity/view-role", {
    method: "POST",
    role,
    body: JSON.stringify({ viewRole })
  });
}

// 这个函数读取绑定关系。
export function fetchBinding(role: ClientRole) {
  return apiRequest<BindingInfo>("/api/relationship/binding", { role });
}
