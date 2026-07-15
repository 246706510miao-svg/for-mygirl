package com.formygirl.common;

import java.time.Clock;
import java.time.ZoneId;
import org.springframework.context.annotation.Bean;
import org.springframework.context.annotation.Configuration;

@Configuration
public class AppTimeConfiguration {
    // 业务日期统一按上海时区计算，避免 UTC 容器在凌晨读取前一天。
    @Bean
    public Clock appClock() {
        return Clock.system(ZoneId.of("Asia/Shanghai"));
    }
}
