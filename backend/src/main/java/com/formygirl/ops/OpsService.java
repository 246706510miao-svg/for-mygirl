package com.formygirl.ops;

import com.formygirl.common.JsonSupport;
import com.formygirl.feishu.FeishuConfigService;
import com.formygirl.persistence.BusinessRepository;
import com.formygirl.thirdclient.ThirdWorkflowClient;
import java.time.LocalDate;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;

@Service
public class OpsService {
    private final BusinessRepository repository;
    private final ThirdWorkflowClient thirdClient;
    private final FeishuConfigService feishuConfigService;
    private final JsonSupport json;

    public OpsService(BusinessRepository repository, ThirdWorkflowClient thirdClient, FeishuConfigService feishuConfigService, JsonSupport json) {
        this.repository = repository;
        this.thirdClient = thirdClient;
        this.feishuConfigService = feishuConfigService;
        this.json = json;
    }

    // 这个函数读取后台首页统计。
    public Map<String, Object> dashboard(LocalDate date) {
        return repository.dashboard(date);
    }

    // 这个函数查询后台记录列表。
    public Map<String, Object> records(LocalDate date, String status, boolean onlyAbnormal, int page, int pageSize) {
        return Map.of(
                "items", repository.adminRecords(date, status, onlyAbnormal, page, pageSize).stream().map(this::adminRecordDto).toList(),
                "page", page,
                "pageSize", pageSize,
                "total", repository.adminRecordCount(date, status, onlyAbnormal)
        );
    }

    // 这个函数查询后台记录详情。
    public Map<String, Object> recordDetail(String recordId) {
        Map<String, Object> record = repository.record(recordId);
        Map<String, Object> draft = record.isEmpty() ? Map.of() : repository.draft(String.valueOf(record.get("final_draft_id")));
        return dto(
                "record", recordDto(record),
                "draft", draft.isEmpty() ? Map.of() : draftDto(draft),
                "display", displayDto(repository.display(recordId)),
                "latestFeishuSync", syncDetailDto(repository.latestFeishuSync(recordId))
        );
    }

    // 这个函数查询每日内容配置。
    public Map<String, Object> dailyContents(String targetUserId, LocalDate date) {
        List<Map<String, Object>> items = repository.dailyContents(targetUserId, date).stream().map(row -> dto(
                "id", row.get("id"),
                "contentType", row.get("content_type"),
                "displayArea", row.get("display_area"),
                "content", json.map(String.valueOf(row.get("content_json"))),
                "resourceId", row.get("resource_id"),
                "enabled", row.get("enabled")
        )).toList();
        return Map.of("targetUserId", targetUserId, "date", date.toString(), "contents", items);
    }

    // 这个函数保存每日内容配置。
    @Transactional
    public Map<String, Object> saveDailyContents(String adminId, String targetUserId, LocalDate date, List<Map<String, Object>> contents) {
        repository.saveDailyContent(targetUserId, adminId, date, contents);
        return Map.of("targetUserId", targetUserId, "date", date.toString(), "savedCount", contents.size(), "updatedAt", java.time.LocalDateTime.now().toString());
    }

    // 这个函数重试飞书同步。
    @Transactional
    public Map<String, Object> retrySync(String recordId, String mode, String requestId) {
        Map<String, Object> record = repository.record(recordId);
        Map<String, Object> latest = repository.latestFeishuSync(recordId);
        Map<String, Object> session = repository.requireSession(String.valueOf(record.get("session_id")));
        FeishuConfigService.WorkflowFeishuContext feishuContext = feishuConfigService.workflowContext(String.valueOf(record.get("user_id")), stringOrNull(session.get("feishu_table_config_id")));
        Map<String, Object> metadata = dto(
                "businessRecordId", recordId,
                "operation", "retry_sync",
                "mode", mode
        );
        metadata.putAll(feishuContext.publicMetadata());
        Map<String, Object> third = thirdClient.invokeAndWait("新增一条记录，重试同步：" + record.getOrDefault("final_text", ""), metadata, feishuContext.privateMetadata());
        String thirdStatus = String.valueOf(third.get("status"));
        String syncStatus = "success".equals(thirdStatus) ? "success" : "failed";
        int retryCount = intValue(latest.get("retry_count"), 0) + 1;
        Map<String, Object> sync = repository.insertFeishuSync(recordId, feishuContext.tableConfigId(), String.valueOf(third.get("session_id")), requestId, syncStatus, "success".equals(syncStatus) ? null : String.valueOf(third.get("error_text")), retryCount, Map.of("retryMode", mode, "thirdStatus", thirdStatus));
        Map<String, Object> display = repository.display(recordId);
        if (!display.isEmpty() && "success".equals(syncStatus)) {
            repository.upsertDisplay(recordId, String.valueOf(display.get("title")), String.valueOf(display.get("summary")), intValue(display.get("score"), 80), "success", json.map(String.valueOf(display.get("admin_content_json"))), json.map(String.valueOf(display.get("display_json"))));
        }
        return dto("recordId", recordId, "recordStatus", "success".equals(syncStatus) ? "success" : record.get("status"), "feishuSync", syncDto(sync), "displayStatus", "success".equals(syncStatus) ? "success" : display.get("display_status"));
    }

    // 这个函数更新用户端展示数据。
    @Transactional
    public Map<String, Object> updateDisplay(String recordId, Map<String, Object> payload) {
        Map<String, Object> current = repository.display(recordId);
        Map<String, Object> adminContent = payload.get("adminContent") instanceof Map<?, ?> map ? castMap(map) : json.map(String.valueOf(current.get("admin_content_json")));
        return displayDto(repository.upsertDisplay(
                recordId,
                String.valueOf(payload.getOrDefault("title", current.get("title"))),
                String.valueOf(payload.getOrDefault("summary", current.get("summary"))),
                intValue(payload.getOrDefault("score", current.get("score")), 80),
                String.valueOf(payload.getOrDefault("displayStatus", current.get("display_status"))),
                adminContent,
                payload
        ));
    }

    // 这个函数转换后台记录列表 DTO。
    private Map<String, Object> adminRecordDto(Map<String, Object> row) {
        return dto("recordId", row.get("record_id"), "recordDate", row.get("record_date"), "summary", row.get("summary"), "status", row.get("status"), "score", row.get("score"), "feishuSyncStatus", row.get("feishu_sync_status"), "retryCount", row.get("retry_count"), "updatedAt", row.get("updated_at"));
    }

    // 这个函数转换正式记录详情 DTO。
    private Map<String, Object> recordDto(Map<String, Object> row) {
        if (row.isEmpty()) {
            return Map.of();
        }
        return dto("id", row.get("id"), "recordDate", row.get("record_date"), "finalText", row.get("final_text"), "aiSummary", row.get("ai_summary"), "aiScore", row.get("ai_score"), "tags", json.list(String.valueOf(row.get("tags_json"))), "status", row.get("status"), "confirmedAt", row.get("confirmed_at"));
    }

    // 这个函数转换草稿 DTO。
    private Map<String, Object> draftDto(Map<String, Object> row) {
        return dto("id", row.get("id"), "versionNo", row.get("version_no"), "draft", json.map(String.valueOf(row.get("draft_json"))));
    }

    // 这个函数转换展示 DTO。
    private Map<String, Object> displayDto(Map<String, Object> row) {
        if (row.isEmpty()) {
            return Map.of();
        }
        return dto("recordId", row.get("record_id"), "title", row.get("title"), "summary", row.get("summary"), "score", row.get("score"), "displayStatus", row.get("display_status"), "adminContent", json.map(String.valueOf(row.get("admin_content_json"))), "updatedAt", row.get("updated_at"));
    }

    // 这个函数转换飞书同步摘要 DTO。
    private Map<String, Object> syncDto(Map<String, Object> row) {
        return dto("id", row.get("id"), "syncStatus", row.get("sync_status"), "feishuRefId", row.get("feishu_ref_id"), "retryCount", row.get("retry_count"), "lastSyncAt", row.get("last_sync_at"), "errorMessage", row.get("error_message"));
    }

    // 这个函数转换飞书同步详情 DTO。
    private Map<String, Object> syncDetailDto(Map<String, Object> row) {
        if (row.isEmpty()) {
            return Map.of();
        }
        Map<String, Object> dto = syncDto(row);
        dto.put("targetType", row.get("target_type"));
        dto.put("targetId", row.get("target_id"));
        dto.put("payload", json.map(String.valueOf(row.get("payload_json"))));
        return dto;
    }

    // 这个函数把对象安全转换为整数。
    private int intValue(Object value, int fallback) {
        if (value instanceof Number number) {
            return number.intValue();
        }
        try {
            return Integer.parseInt(String.valueOf(value));
        } catch (Exception exception) {
            return fallback;
        }
    }

    // 这个函数创建允许空值的 DTO Map。
    private Map<String, Object> dto(Object... entries) {
        Map<String, Object> result = new LinkedHashMap<>();
        for (int index = 0; index + 1 < entries.length; index += 2) {
            result.put(String.valueOf(entries[index]), entries[index + 1]);
        }
        return result;
    }

    // 这个函数把通配 Map 转成字符串键 Map。
    private Map<String, Object> castMap(Map<?, ?> source) {
        Map<String, Object> result = new LinkedHashMap<>();
        source.forEach((key, value) -> result.put(String.valueOf(key), value));
        return result;
    }

    private String stringOrNull(Object value) {
        if (value == null) {
            return null;
        }
        String text = String.valueOf(value);
        return text.isBlank() || "null".equals(text) ? null : text;
    }
}
