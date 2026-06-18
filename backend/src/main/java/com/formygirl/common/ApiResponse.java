package com.formygirl.common;

public record ApiResponse<T>(String code, String message, T data, String requestId) {
    // 这个函数创建成功响应。
    public static <T> ApiResponse<T> ok(T data, String requestId) {
        return new ApiResponse<>("OK", "success", data, requestId);
    }

    // 这个函数创建创建成功响应。
    public static <T> ApiResponse<T> created(T data, String requestId) {
        return new ApiResponse<>("CREATED", "success", data, requestId);
    }

    // 这个函数创建失败响应。
    public static <T> ApiResponse<T> error(String code, String message, T data, String requestId) {
        return new ApiResponse<>(code, message, data, requestId);
    }
}
