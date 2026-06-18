package com.formygirl.common;

import java.util.UUID;

public final class Ids {
    private Ids() {
    }

    // 这个函数生成带业务前缀的短 ID。
    public static String newId(String prefix) {
        return prefix + "_" + UUID.randomUUID().toString().replace("-", "").substring(0, 24);
    }
}
