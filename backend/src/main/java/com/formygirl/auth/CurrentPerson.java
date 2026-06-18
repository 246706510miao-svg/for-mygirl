package com.formygirl.auth;

public record CurrentPerson(String id, String role, String displayName) {
    // 这个函数判断当前登录人是否是管理员。
    public boolean isAdmin() {
        return "ADMIN".equals(role);
    }
}
