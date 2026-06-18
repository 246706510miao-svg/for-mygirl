package com.formygirl.common;

import java.util.UUID;

public final class RequestIds {
    public static final String HEADER = "X-Request-Id";
    public static final String ATTRIBUTE = "requestId";

    private RequestIds() {
    }

    // 这个函数生成后端请求追踪 ID。
    public static String newRequestId() {
        return "req_" + UUID.randomUUID().toString().replace("-", "").substring(0, 16);
    }
}
