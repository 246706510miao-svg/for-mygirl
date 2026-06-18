package com.formygirl.record;

import com.formygirl.auth.CurrentPerson;
import com.formygirl.common.ApiException;
import com.formygirl.common.JsonSupport;
import com.formygirl.thirdclient.ThirdWorkflowClient;
import java.time.LocalDate;
import java.util.ArrayList;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;
import org.springframework.http.HttpStatus;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;

@Service
public class RecordService {
    private final BusinessRepository repository;
    private final ThirdWorkflowClient thirdClient;
    private final JsonSupport json;

    public RecordService(BusinessRepository repository, ThirdWorkflowClient thirdClient, JsonSupport json) {
        this.repository = repository;
        this.thirdClient = thirdClient;
        this.json = json;
    }

    // 这个函数组装用户首页接口数据。
    public Map<String, Object> home(CurrentPerson person, LocalDate date) {
        List<Map<String, Object>> contents = repository.dailyContents(person.id(), date);
        Map<String, Object> homeContent = new LinkedHashMap<>(Map.of("mainText", "今天也认真照顾自己", "subText", "把完成过的小事写下来，慢慢看到自己的节奏。"));
        Map<String, Object> recordGuide = new LinkedHashMap<>(Map.of("title", "今日记录引导", "items", List.of("完成了什么", "遇到什么阻力", "明天想怎么调整")));
        for (Map<String, Object> row : contents) {
            String type = String.valueOf(row.get("content_type"));
            String area = String.valueOf(row.get("display_area"));
            Map<String, Object> content = json.map(String.valueOf(row.get("content_json")));
            if ("home".equals(area) && "text".equals(type)) {
                homeContent.putAll(content);
            }
            if ("record_page".equals(area) && "reminder".equals(type)) {
                recordGuide.putAll(content);
            }
        }
        return Map.of(
                "date", date.toString(),
                "homeContent", homeContent,
                "recordGuide", recordGuide,
                "latestRecord", displayDto(repository.latestDisplay(person.id()))
        );
    }

    // 这个函数组装用户最近记录列表。
    public Map<String, Object> userRecords(CurrentPerson person, LocalDate fromDate, LocalDate toDate, int page, int pageSize) {
        List<Map<String, Object>> rows = repository.userRecords(person.id(), fromDate, toDate, page, pageSize);
        return Map.of(
                "items", rows.stream().map(this::displayDto).toList(),
                "page", page,
                "pageSize", pageSize,
                "total", repository.userRecordCount(person.id(), fromDate, toDate)
        );
    }

    // 这个函数创建记录会话。
    @Transactional
    public Map<String, Object> createSession(CurrentPerson person, LocalDate recordDate, String requestId) {
        return sessionDto(repository.createSession(person.id(), recordDate, requestId));
    }

    // 这个函数处理文本输入或修改指令并生成草稿。
    @Transactional
    public Map<String, Object> sendMessage(CurrentPerson person, String sessionId, String clientMessageId, String content, String requestId) {
        Map<String, Object> session = requireOwnedSession(person, sessionId);
        Map<String, Object> existing = repository.findMessageByClientId(sessionId, clientMessageId);
        if (!existing.isEmpty()) {
            return sessionDetail(sessionId);
        }
        Map<String, Object> userMessage = repository.insertMessage(sessionId, "user", "text", content, null, clientMessageId, null, requestId);
        Map<String, Object> third = thirdClient.invokeAndWait("生成记录草稿：" + draftContext(sessionId, content), Map.of(
                "businessSessionId", sessionId,
                "operation", "draft_generate",
                "idempotencyKey", clientMessageId
        ));
        String thirdSessionId = String.valueOf(third.get("session_id"));
        Map<String, Object> draftData = extractDraft(thirdSessionId, content, session);
        repository.replaceActiveDrafts(sessionId);
        Map<String, Object> draft = repository.insertDraft(sessionId, draftData, String.valueOf(draftData.get("previewText")), thirdSessionId, requestId);
        Map<String, Object> aiMessage = repository.insertMessage(sessionId, "ai", "text", "我整理了一版草稿，你可以直接确认，也可以继续告诉我怎么改。", null, null, thirdSessionId, requestId);
        return Map.of("session", sessionDto(repository.requireSession(sessionId)), "userMessage", messageDto(userMessage), "aiMessage", messageDto(aiMessage), "draft", draftDto(draft));
    }

    // 这个函数查询记录会话详情。
    public Map<String, Object> sessionDetail(String sessionId) {
        Map<String, Object> session = repository.requireSession(sessionId);
        if (session.isEmpty()) {
            throw new ApiException(HttpStatus.NOT_FOUND, "NOT_FOUND", "记录会话不存在");
        }
        Map<String, Object> currentDraft = repository.currentDraft(sessionId);
        return Map.of(
                "session", sessionDto(session),
                "messages", repository.sessionMessages(sessionId).stream().map(this::messageDto).toList(),
                "currentDraft", currentDraft.isEmpty() ? Map.of() : draftDto(currentDraft)
        );
    }

    // 这个函数确认草稿并写入本地正式记录与飞书同步状态。
    @Transactional
    public Map<String, Object> confirm(CurrentPerson person, String sessionId, String draftId, String clientConfirmId, String requestId) {
        Map<String, Object> session = requireOwnedSession(person, sessionId);
        Map<String, Object> existing = repository.findRecordByConfirmId(sessionId, clientConfirmId);
        if (!existing.isEmpty()) {
            return confirmResult(existing);
        }
        Map<String, Object> draft = repository.draft(draftId);
        if (draft.isEmpty() || !sessionId.equals(String.valueOf(draft.get("session_id")))) {
            throw new ApiException(HttpStatus.NOT_FOUND, "NOT_FOUND", "草稿不存在");
        }
        repository.confirmDraft(sessionId, draftId);
        Map<String, Object> third;
        try {
            third = invokeConfirmWorkflow(sessionId, draft, clientConfirmId);
        } catch (Exception exception) {
            third = dto("status", "failed", "session_id", null, "error_text", exception.getMessage());
        }
        String thirdStatus = String.valueOf(third.get("status"));
        Object thirdSessionValue = third.get("session_id");
        String thirdSessionId = thirdSessionValue == null ? null : String.valueOf(thirdSessionValue);
        String recordStatus = "success".equals(thirdStatus) ? "success" : "sync_failed";
        String errorMessage = "success".equals(thirdStatus) ? null : String.valueOf(third.getOrDefault("error_text", "third workflow 未成功完成"));
        Map<String, Object> record = repository.insertDailyRecord(session, draft, clientConfirmId, thirdSessionId, requestId, recordStatus);
        Map<String, Object> draftJson = json.map(String.valueOf(draft.get("draft_json")));
        Map<String, Object> syncPayload = dto("thirdStatus", thirdStatus, "thirdSessionId", thirdSessionId);
        Map<String, Object> sync = repository.insertFeishuSync(String.valueOf(record.get("id")), thirdSessionId, requestId, "success".equals(recordStatus) ? "success" : "failed", errorMessage, "success".equals(recordStatus) ? 0 : 1, syncPayload);
        Map<String, Object> display = repository.upsertDisplay(
                String.valueOf(record.get("id")),
                String.valueOf(draftJson.getOrDefault("title", "今日自律记录")),
                String.valueOf(draftJson.getOrDefault("summary", draft.get("preview_text"))),
                intValue(draftJson.get("score"), 80),
                recordStatus,
                Map.of(),
                draftJson
        );
        repository.markSessionConfirmed(sessionId);
        Map<String, Object> reply = repository.insertMessage(sessionId, "system", "text", "记录已保存，飞书同步状态为 " + recordStatus + "。", null, null, thirdSessionId, requestId);
        return Map.of("session", sessionDto(repository.requireSession(sessionId)), "record", recordDto(record), "feishuSync", syncDto(sync), "display", displayDto(display), "replyMessage", messageDto(reply));
    }

    // 这个函数取消记录会话。
    @Transactional
    public Map<String, Object> cancel(CurrentPerson person, String sessionId) {
        Map<String, Object> session = requireOwnedSession(person, sessionId);
        String status = String.valueOf(session.get("status"));
        if (!List.of("editing", "previewing").contains(status)) {
            throw new ApiException(HttpStatus.CONFLICT, "CONFLICT", "当前会话状态不允许取消");
        }
        return sessionDto(repository.cancelSession(sessionId));
    }

    // 这个函数校验会话归属。
    private Map<String, Object> requireOwnedSession(CurrentPerson person, String sessionId) {
        Map<String, Object> session = repository.requireSession(sessionId);
        if (session.isEmpty()) {
            throw new ApiException(HttpStatus.NOT_FOUND, "NOT_FOUND", "记录会话不存在");
        }
        if (!person.id().equals(String.valueOf(session.get("user_id")))) {
            throw new ApiException(HttpStatus.FORBIDDEN, "FORBIDDEN", "当前角色无权限");
        }
        return session;
    }

    // 这个函数构造提交给 third 的草稿上下文。
    private String draftContext(String sessionId, String content) {
        List<String> messages = repository.sessionMessages(sessionId).stream().map(row -> row.get("sender") + ":" + row.get("content")).toList();
        return String.join("\n", messages) + "\n本轮输入：" + content;
    }

    // 这个函数从 third artifact 中提取草稿。
    private Map<String, Object> extractDraft(String thirdSessionId, String content, Map<String, Object> session) {
        try {
            Map<String, Object> artifacts = thirdClient.artifacts(thirdSessionId);
            Object items = artifacts.get("artifacts");
            if (items instanceof List<?> list) {
                for (Object item : list) {
                    if (item instanceof Map<?, ?> map && "record.draft".equals(String.valueOf(map.get("artifact_key")))) {
                        Object data = map.get("data_json");
                        if (data instanceof Map<?, ?> dataMap) {
                            return castMap(dataMap);
                        }
                    }
                }
            }
        } catch (Exception ignored) {
            // third 成功响应但 artifact 查询失败时，使用本地兜底草稿，避免消息接口中断。
        }
        return Map.of("title", "今日自律记录", "recordDate", String.valueOf(session.get("record_date")), "summary", content, "score", 80, "tags", List.of("记录"), "previewText", content);
    }

    // 这个函数提交确认写入 workflow，必要时自动通过 third 确认门。
    private Map<String, Object> invokeConfirmWorkflow(String sessionId, Map<String, Object> draft, String clientConfirmId) {
        Map<String, Object> third = thirdClient.invokeAndWait("新增一条记录，事项名称为今日自律记录，总结为" + draft.get("preview_text"), Map.of(
                "businessSessionId", sessionId,
                "operation", "confirm_sync",
                "idempotencyKey", clientConfirmId
        ));
        if ("waiting_user".equals(String.valueOf(third.get("status"))) && third.get("confirmation") instanceof Map<?, ?> confirmation) {
            Object confirmationId = confirmation.get("confirmation_id");
            if (confirmationId != null) {
                return thirdClient.resumeAndWait(String.valueOf(third.get("session_id")), String.valueOf(confirmationId), "业务前端已确认写入");
            }
        }
        return third;
    }

    // 这个函数根据已有正式记录返回确认结果。
    private Map<String, Object> confirmResult(Map<String, Object> record) {
        String recordId = String.valueOf(record.get("id"));
        return Map.of(
                "session", sessionDto(repository.requireSession(String.valueOf(record.get("session_id")))),
                "record", recordDto(record),
                "feishuSync", syncDto(repository.latestFeishuSync(recordId)),
                "display", displayDto(repository.display(recordId))
        );
    }

    // 这个函数转换会话 DTO。
    private Map<String, Object> sessionDto(Map<String, Object> row) {
        return dto("id", row.get("id"), "status", row.get("status"), "currentDraftId", row.get("current_draft_id"), "createdAt", row.get("created_at"), "updatedAt", row.get("updated_at"));
    }

    // 这个函数转换消息 DTO。
    private Map<String, Object> messageDto(Map<String, Object> row) {
        return dto("id", row.get("id"), "sessionId", row.get("session_id"), "sender", row.get("sender"), "inputType", row.get("input_type"), "content", row.get("content"), "asrText", row.get("asr_text"), "sequenceNo", row.get("sequence_no"), "createdAt", row.get("created_at"));
    }

    // 这个函数转换草稿 DTO。
    private Map<String, Object> draftDto(Map<String, Object> row) {
        return dto("id", row.get("id"), "sessionId", row.get("session_id"), "versionNo", row.get("version_no"), "status", row.get("status"), "previewText", row.get("preview_text"), "draft", json.map(String.valueOf(row.get("draft_json"))), "createdAt", row.get("created_at"));
    }

    // 这个函数转换正式记录 DTO。
    private Map<String, Object> recordDto(Map<String, Object> row) {
        return dto("id", row.get("id"), "recordDate", row.get("record_date"), "status", row.get("status"), "finalText", row.get("final_text"), "aiSummary", row.get("ai_summary"), "aiScore", row.get("ai_score"), "tags", json.list(String.valueOf(row.get("tags_json"))), "confirmedAt", row.get("confirmed_at"));
    }

    // 这个函数转换展示 DTO。
    private Map<String, Object> displayDto(Map<String, Object> row) {
        if (row == null || row.isEmpty()) {
            return Map.of();
        }
        return dto("recordId", row.get("record_id"), "recordDate", row.get("record_date"), "title", row.get("title"), "summary", row.get("summary"), "score", row.get("score"), "displayStatus", row.get("display_status"), "adminContent", json.map(String.valueOf(row.get("admin_content_json"))), "updatedAt", row.get("updated_at"));
    }

    // 这个函数转换飞书同步 DTO。
    private Map<String, Object> syncDto(Map<String, Object> row) {
        if (row == null || row.isEmpty()) {
            return Map.of();
        }
        return dto("id", row.get("id"), "syncStatus", row.get("sync_status"), "targetType", row.get("target_type"), "targetId", row.get("target_id"), "feishuRefId", row.get("feishu_ref_id"), "retryCount", row.get("retry_count"), "lastSyncAt", row.get("last_sync_at"), "errorMessage", row.get("error_message"));
    }

    // 这个函数创建允许空值的 DTO Map。
    private Map<String, Object> dto(Object... entries) {
        Map<String, Object> result = new LinkedHashMap<>();
        for (int index = 0; index + 1 < entries.length; index += 2) {
            result.put(String.valueOf(entries[index]), entries[index + 1]);
        }
        return result;
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

    // 这个函数把通配 Map 转成字符串键 Map。
    private Map<String, Object> castMap(Map<?, ?> source) {
        Map<String, Object> result = new LinkedHashMap<>();
        source.forEach((key, value) -> result.put(String.valueOf(key), value));
        return result;
    }
}
