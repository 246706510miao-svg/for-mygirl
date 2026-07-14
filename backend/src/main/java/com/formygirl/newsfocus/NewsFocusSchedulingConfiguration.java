package com.formygirl.newsfocus;

import org.springframework.context.annotation.Bean;
import org.springframework.context.annotation.Configuration;
import org.springframework.scheduling.TaskScheduler;
import org.springframework.scheduling.concurrent.ThreadPoolTaskScheduler;

@Configuration
public class NewsFocusSchedulingConfiguration {
    // 每日热门使用独立调度线程，不能被记录工作流的轮询占用。
    @Bean("newsFocusTaskScheduler")
    public TaskScheduler newsFocusTaskScheduler() {
        ThreadPoolTaskScheduler scheduler = new ThreadPoolTaskScheduler();
        scheduler.setPoolSize(1);
        scheduler.setThreadNamePrefix("news-focus-");
        scheduler.initialize();
        return scheduler;
    }
}
