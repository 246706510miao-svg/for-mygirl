package com.formygirl.newsfocus;

import java.time.LocalDate;
import java.time.ZoneId;
import org.springframework.scheduling.annotation.Scheduled;
import org.springframework.stereotype.Component;

@Component
public class NewsFocusRefreshScheduler {
    private static final ZoneId SHANGHAI = ZoneId.of("Asia/Shanghai");
    private final NewsFocusService service;

    public NewsFocusRefreshScheduler(NewsFocusService service) {
        this.service = service;
    }

    // 这个函数每天上海时间 07:30 刷新共享热门。
    @Scheduled(cron = "${app.news-focus-cron:0 30 7 * * *}", zone = "Asia/Shanghai", scheduler = "newsFocusTaskScheduler")
    public void refreshDaily() {
        service.refresh(LocalDate.now(SHANGHAI));
    }
}
