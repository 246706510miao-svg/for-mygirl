package com.formygirl.record;

import org.springframework.scheduling.annotation.Scheduled;
import org.springframework.stereotype.Component;

@Component
public class RecordWorkflowProcessor {
    private final RecordService recordService;

    public RecordWorkflowProcessor(RecordService recordService) {
        this.recordService = recordService;
    }

    // 这个函数把 SpringBoot 侧的 record workflow 任务推进到业务表。
    @Scheduled(fixedDelayString = "${app.record-workflow-poll-delay-ms:1000}")
    public void processPendingTasks() {
        recordService.processPendingWorkflowTasks();
    }
}
