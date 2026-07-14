package com.formygirl.newsfocus;

import java.time.LocalDate;
import java.time.ZoneId;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.boot.context.event.ApplicationReadyEvent;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.context.event.EventListener;
import org.springframework.stereotype.Component;

@Component
public class NewsFocusStartupRefresh {
    private static final ZoneId SHANGHAI = ZoneId.of("Asia/Shanghai");
    private static final Logger log = LoggerFactory.getLogger(NewsFocusStartupRefresh.class);
    private final NewsFocusService service;
    private final boolean runOnStartup;

    public NewsFocusStartupRefresh(NewsFocusService service, @Value("${app.news-focus-run-on-startup:false}") boolean runOnStartup) {
        this.service = service;
        this.runOnStartup = runOnStartup;
    }

    // 仅在显式环境开关打开时执行一次，供本地验证和受控补跑使用。
    @EventListener(ApplicationReadyEvent.class)
    public void refreshOnce() {
        if (!runOnStartup) {
            return;
        }
        log.info("news focus startup refresh requested");
        service.refresh(LocalDate.now(SHANGHAI));
    }
}
