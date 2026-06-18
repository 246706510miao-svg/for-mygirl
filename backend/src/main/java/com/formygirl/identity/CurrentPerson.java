package com.formygirl.identity;

public record CurrentPerson(String id, String role, String displayName) {
    // 这个函数判断当前登录人是否是后台运维人员。
    public boolean isOpsAdmin() {
        return "OPS_ADMIN".equals(role) || "ADMIN".equals(role);
    }
}
