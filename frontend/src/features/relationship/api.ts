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

// 这个函数向另一个账号发起绑定邀请。
export function inviteBindingUser(role: ClientRole, targetLoginName: string) {
  return apiRequest<Record<string, unknown>>("/api/relationship/invitations", {
    method: "POST",
    role,
    body: JSON.stringify({ targetLoginName })
  });
}

// 这个函数接受绑定邀请。
export function acceptBindingInvitation(role: ClientRole, bindingId: string) {
  return apiRequest<IdentityContext>(`/api/relationship/invitations/${bindingId}/accept`, {
    method: "POST",
    role
  });
}

// 这个函数拒绝绑定邀请。
export function rejectBindingInvitation(role: ClientRole, bindingId: string) {
  return apiRequest<IdentityContext>(`/api/relationship/invitations/${bindingId}/reject`, {
    method: "POST",
    role
  });
}

// 这个函数取消已发出的绑定邀请。
export function cancelBindingInvitation(role: ClientRole, bindingId: string) {
  return apiRequest<IdentityContext>(`/api/relationship/invitations/${bindingId}/cancel`, {
    method: "POST",
    role
  });
}
