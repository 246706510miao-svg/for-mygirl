package com.formygirl.common;

import jakarta.servlet.http.HttpServletRequest;
import org.springframework.http.HttpStatus;
import org.springframework.http.ResponseEntity;
import org.springframework.web.bind.MethodArgumentNotValidException;
import org.springframework.web.bind.annotation.ExceptionHandler;
import org.springframework.web.bind.annotation.RestControllerAdvice;

@RestControllerAdvice
public class GlobalExceptionHandler {
    // 这个函数把业务异常转换为接口文档约定的失败响应。
    @ExceptionHandler(ApiException.class)
    public ResponseEntity<ApiResponse<Object>> handleApiException(ApiException exception, HttpServletRequest request) {
        return ResponseEntity.status(exception.getStatus())
                .body(ApiResponse.error(exception.getCode(), exception.getMessage(), null, requestId(request)));
    }

    // 这个函数把参数校验异常转换为统一失败响应。
    @ExceptionHandler(MethodArgumentNotValidException.class)
    public ResponseEntity<ApiResponse<Object>> handleValidation(MethodArgumentNotValidException exception, HttpServletRequest request) {
        return ResponseEntity.status(HttpStatus.UNPROCESSABLE_ENTITY)
                .body(ApiResponse.error("VALIDATION_ERROR", "请求参数不合法", exception.getBindingResult().getFieldErrors(), requestId(request)));
    }

    // 这个函数兜底处理未预期异常。
    @ExceptionHandler(Exception.class)
    public ResponseEntity<ApiResponse<Object>> handleException(Exception exception, HttpServletRequest request) {
        return ResponseEntity.status(HttpStatus.INTERNAL_SERVER_ERROR)
                .body(ApiResponse.error("INTERNAL_ERROR", exception.getMessage(), null, requestId(request)));
    }

    // 这个函数从请求上下文读取 requestId。
    private String requestId(HttpServletRequest request) {
        Object value = request.getAttribute(RequestIds.ATTRIBUTE);
        return value == null ? "" : value.toString();
    }
}
