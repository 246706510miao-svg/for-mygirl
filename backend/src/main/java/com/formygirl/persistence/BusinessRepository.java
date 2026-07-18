package com.formygirl.persistence;

import com.formygirl.common.Ids;
import com.formygirl.common.JsonSupport;
import java.sql.Date;
import java.sql.Timestamp;
import java.time.LocalDate;
import java.time.LocalDateTime;
import java.util.ArrayList;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;
import org.springframework.dao.EmptyResultDataAccessException;
import org.springframework.jdbc.core.JdbcTemplate;
import org.springframework.stereotype.Repository;

@Repository
public class BusinessRepository {
    private final JdbcTemplate jdbcTemplate;
    private final JsonSupport json;

    public BusinessRepository(JdbcTemplate jdbcTemplate, JsonSupport json) {
        this.jdbcTemplate = jdbcTemplate;
        this.json = json;
    }

    // 这个函数查询用户首页当天内容和默认内容。
    public List<Map<String, Object>> dailyContents(String userId, LocalDate date) {
        return jdbcTemplate.queryForList(
                """
                SELECT * FROM DAILY_CONTENT
                WHERE target_user_id = ? AND enabled = TRUE AND content_date IN (?, ?)
                ORDER BY content_date DESC
                """,
                userId,
                Date.valueOf(date),
                Date.valueOf("2099-12-31")
        );
    }

    // 这个函数查询用户最近一条展示记录。
    public Map<String, Object> latestDisplay(String userId) {
        return queryOne(
                """
                SELECT dr.id AS record_id, dr.record_date, rd.title, rd.summary, rd.score, rd.display_status, rd.admin_content_json, rd.updated_at
                FROM DAILY_RECORD dr
                JOIN RECORD_DISPLAY rd ON rd.record_id = dr.id
                WHERE dr.user_id = ?
                ORDER BY dr.record_date DESC, dr.created_at DESC
                LIMIT 1
                """,
                userId
        );
    }

    // 这个函数分页查询用户最近记录展示数据。
    public List<Map<String, Object>> userRecords(String userId, LocalDate fromDate, LocalDate toDate, int page, int pageSize) {
        int offset = Math.max(0, page - 1) * pageSize;
        return jdbcTemplate.queryForList(
                """
                SELECT dr.id AS record_id, dr.record_date, rd.title, rd.summary, rd.score, rd.display_status, rd.admin_content_json, rd.updated_at
                FROM DAILY_RECORD dr
                JOIN RECORD_DISPLAY rd ON rd.record_id = dr.id
                WHERE dr.user_id = ? AND dr.record_date BETWEEN ? AND ?
                ORDER BY dr.record_date DESC, dr.created_at DESC
                LIMIT ? OFFSET ?
                """,
                userId,
                Date.valueOf(fromDate),
                Date.valueOf(toDate),
                pageSize,
                offset
        );
    }

    // 这个函数统计用户最近记录数量。
    public int userRecordCount(String userId, LocalDate fromDate, LocalDate toDate) {
        Integer count = jdbcTemplate.queryForObject(
                "SELECT COUNT(*) FROM DAILY_RECORD WHERE user_id = ? AND record_date BETWEEN ? AND ?",
                Integer.class,
                userId,
                Date.valueOf(fromDate),
                Date.valueOf(toDate)
        );
        return count == null ? 0 : count;
    }

    // 这个函数创建记录会话。
    public Map<String, Object> createSession(String userId, LocalDate recordDate, String requestId, String feishuTableConfigId) {
        String id = Ids.newId("session");
        LocalDateTime now = LocalDateTime.now();
        jdbcTemplate.update(
                "INSERT INTO RECORD_SESSION (id, user_id, record_date, status, current_draft_id, request_id, feishu_table_config_id, created_at, updated_at) VALUES (?, ?, ?, 'editing', NULL, ?, ?, ?, ?)",
                id,
                userId,
                Date.valueOf(recordDate),
                requestId,
                feishuTableConfigId,
                Timestamp.valueOf(now),
                Timestamp.valueOf(now)
        );
        return requireSession(id);
    }

    // 这个函数读取记录会话。
    public Map<String, Object> requireSession(String sessionId) {
        return queryOne("SELECT * FROM RECORD_SESSION WHERE id = ?", sessionId);
    }

    // 这个函数按客户端消息幂等 ID 查找已有消息。
    public Map<String, Object> findMessageByClientId(String sessionId, String clientMessageId) {
        return queryOne("SELECT * FROM RECORD_MESSAGE WHERE session_id = ? AND client_message_id = ?", sessionId, clientMessageId);
    }

    // 这个函数读取单条记录会话消息。
    public Map<String, Object> message(String messageId) {
        return queryOne("SELECT * FROM RECORD_MESSAGE WHERE id = ?", messageId);
    }

    // 这个函数写入记录会话消息。
    public Map<String, Object> insertMessage(String sessionId, String sender, String inputType, String content, String asrText, String clientMessageId, String thirdSessionId, String requestId) {
        String id = Ids.newId("msg");
        int sequenceNo = nextMessageSequence(sessionId);
        jdbcTemplate.update(
                """
                INSERT INTO RECORD_MESSAGE (id, session_id, sender, input_type, content, asr_text, sequence_no, client_message_id, third_session_id, request_id, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                id,
                sessionId,
                sender,
                inputType,
                content,
                asrText,
                sequenceNo,
                clientMessageId,
                thirdSessionId,
                requestId,
                Timestamp.valueOf(LocalDateTime.now())
        );
        return queryOne("SELECT * FROM RECORD_MESSAGE WHERE id = ?", id);
    }

    // 这个函数在 third 提交成功后回写消息关联的 third session。
    public Map<String, Object> updateMessageThirdSession(String messageId, String thirdSessionId) {
        jdbcTemplate.update("UPDATE RECORD_MESSAGE SET third_session_id = ? WHERE id = ?", thirdSessionId, messageId);
        return message(messageId);
    }

    // 这个函数创建 backend 侧的 third workflow 跟踪任务。
    public Map<String, Object> createWorkflowTask(
            String sessionId,
            String triggerType,
            String clientActionId,
            String sourceMessageId,
            String draftId,
            String thirdSessionId,
            String confirmationId,
            Boolean approved,
            String status,
            String requestId
    ) {
        return createWorkflowTask(sessionId, triggerType, clientActionId, sourceMessageId, draftId, null, null, thirdSessionId, confirmationId, approved, status, requestId);
    }

    // 这个函数创建带正式记录/同步记录引用的 workflow 跟踪任务。
    public Map<String, Object> createWorkflowTask(
            String sessionId,
            String triggerType,
            String clientActionId,
            String sourceMessageId,
            String draftId,
            String recordId,
            String syncId,
            String thirdSessionId,
            String confirmationId,
            Boolean approved,
            String status,
            String requestId
    ) {
        Map<String, Object> existing = findWorkflowTask(sessionId, triggerType, clientActionId);
        if (!existing.isEmpty()) {
            return existing;
        }
        String id = Ids.newId("task");
        LocalDateTime now = LocalDateTime.now();
        jdbcTemplate.update(
                """
                INSERT INTO RECORD_WORKFLOW_TASK (
                  id, session_id, trigger_type, client_action_id, source_message_id, draft_id, record_id, sync_id,
                  third_session_id, confirmation_id, approved, status, error_text, request_id,
                  created_at, updated_at
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, NULL, ?, ?, ?)
                """,
                id,
                sessionId,
                triggerType,
                clientActionId,
                sourceMessageId,
                draftId,
                recordId,
                syncId,
                thirdSessionId,
                confirmationId,
                approved,
                status,
                requestId,
                Timestamp.valueOf(now),
                Timestamp.valueOf(now)
        );
        return workflowTask(id);
    }

    // 这个函数读取单个 workflow 跟踪任务。
    public Map<String, Object> workflowTask(String taskId) {
        return queryOne("SELECT * FROM RECORD_WORKFLOW_TASK WHERE id = ?", taskId);
    }

    // 这个函数按业务幂等键读取 workflow 跟踪任务。
    public Map<String, Object> findWorkflowTask(String sessionId, String triggerType, String clientActionId) {
        return queryOne("SELECT * FROM RECORD_WORKFLOW_TASK WHERE session_id = ? AND trigger_type = ? AND client_action_id = ?", sessionId, triggerType, clientActionId);
    }

    // 这个函数读取会话最近一次 workflow 跟踪任务。
    public Map<String, Object> latestWorkflowTask(String sessionId) {
        return queryOne("SELECT * FROM RECORD_WORKFLOW_TASK WHERE session_id = ? ORDER BY task_sequence DESC LIMIT 1", sessionId);
    }

    // 这个函数扫描需要继续查询 third 状态的任务。
    public List<Map<String, Object>> pendingWorkflowTasks(int limit) {
        return jdbcTemplate.queryForList(
                """
                SELECT * FROM RECORD_WORKFLOW_TASK
                WHERE status IN ('submitted', 'running')
                  AND third_session_id IS NOT NULL
                ORDER BY task_sequence ASC
                LIMIT ?
                """,
                Math.max(1, limit)
        );
    }

    // 这个函数更新 workflow 跟踪任务状态。
    public Map<String, Object> updateWorkflowTaskStatus(String taskId, String status, String errorText) {
        jdbcTemplate.update(
                "UPDATE RECORD_WORKFLOW_TASK SET status = ?, error_text = ?, updated_at = ? WHERE id = ?",
                status,
                errorText,
                Timestamp.valueOf(LocalDateTime.now()),
                taskId
        );
        return workflowTask(taskId);
    }

    // 这个函数记录 third 确认门信息。
    public Map<String, Object> markWorkflowTaskWaitingUser(String taskId, String confirmationId, String draftId) {
        jdbcTemplate.update(
                "UPDATE RECORD_WORKFLOW_TASK SET status = 'waiting_user', confirmation_id = ?, draft_id = ?, error_text = NULL, updated_at = ? WHERE id = ?",
                confirmationId,
                draftId,
                Timestamp.valueOf(LocalDateTime.now()),
                taskId
        );
        return workflowTask(taskId);
    }

    // 这个函数把旧草稿标记为 replaced。
    public void replaceActiveDrafts(String sessionId) {
        jdbcTemplate.update("UPDATE RECORD_DRAFT SET status = 'replaced' WHERE session_id = ? AND status = 'active'", sessionId);
    }

    // 这个函数插入 AI 生成的新草稿。
    public Map<String, Object> insertDraft(String sessionId, Map<String, Object> draft, String previewText, String thirdSessionId, String requestId) {
        String id = Ids.newId("draft");
        int versionNo = nextDraftVersion(sessionId);
        jdbcTemplate.update(
                """
                INSERT INTO RECORD_DRAFT (id, session_id, version_no, draft_json, preview_text, status, third_session_id, request_id, created_at)
                VALUES (?, ?, ?, CAST(? AS JSON), ?, 'active', ?, ?, ?)
                """,
                id,
                sessionId,
                versionNo,
                json.stringify(draft),
                previewText,
                thirdSessionId,
                requestId,
                Timestamp.valueOf(LocalDateTime.now())
        );
        jdbcTemplate.update("UPDATE RECORD_SESSION SET status = 'previewing', current_draft_id = ?, updated_at = ? WHERE id = ?", id, Timestamp.valueOf(LocalDateTime.now()), sessionId);
        return queryOne("SELECT * FROM RECORD_DRAFT WHERE id = ?", id);
    }

    // 这个函数读取当前草稿。
    public Map<String, Object> currentDraft(String sessionId) {
        return queryOne("SELECT * FROM RECORD_DRAFT WHERE session_id = ? AND status = 'active' ORDER BY version_no DESC LIMIT 1", sessionId);
    }

    // 这个函数列出会话消息。
    public List<Map<String, Object>> sessionMessages(String sessionId) {
        return jdbcTemplate.queryForList("SELECT * FROM RECORD_MESSAGE WHERE session_id = ? ORDER BY sequence_no ASC", sessionId);
    }

    // 这个函数列出会话草稿。
    public List<Map<String, Object>> sessionDrafts(String sessionId) {
        return jdbcTemplate.queryForList("SELECT * FROM RECORD_DRAFT WHERE session_id = ? ORDER BY version_no ASC", sessionId);
    }

    // 这个函数根据确认幂等 ID 查找正式记录。
    public Map<String, Object> findRecordByConfirmId(String sessionId, String clientConfirmId) {
        return queryOne("SELECT * FROM DAILY_RECORD WHERE session_id = ? AND client_confirm_id = ?", sessionId, clientConfirmId);
    }

    // 这个函数读取会话对应的正式记录。
    public Map<String, Object> findRecordBySession(String sessionId) {
        return queryOne("SELECT * FROM DAILY_RECORD WHERE session_id = ? ORDER BY created_at DESC LIMIT 1", sessionId);
    }

    // 这个函数把指定草稿标记为 confirmed。
    public void confirmDraft(String sessionId, String draftId) {
        jdbcTemplate.update("UPDATE RECORD_DRAFT SET status = CASE WHEN id = ? THEN 'confirmed' ELSE 'replaced' END WHERE session_id = ?", draftId, sessionId);
        jdbcTemplate.update("UPDATE RECORD_SESSION SET status = 'confirming', current_draft_id = ?, updated_at = ? WHERE id = ?", draftId, Timestamp.valueOf(LocalDateTime.now()), sessionId);
    }

    // 这个函数把等待确认的草稿恢复为可继续编辑状态。
    public Map<String, Object> reopenDraft(String sessionId, String draftId) {
        jdbcTemplate.update("UPDATE RECORD_DRAFT SET status = CASE WHEN id = ? THEN 'active' ELSE 'replaced' END WHERE session_id = ?", draftId, sessionId);
        jdbcTemplate.update("UPDATE RECORD_SESSION SET status = 'previewing', current_draft_id = ?, updated_at = ? WHERE id = ?", draftId, Timestamp.valueOf(LocalDateTime.now()), sessionId);
        return draft(draftId);
    }

    // 这个函数创建正式记录。
    public Map<String, Object> insertDailyRecord(Map<String, Object> session, Map<String, Object> draft, String clientConfirmId, String thirdSessionId, String requestId, String status) {
        String id = Ids.newId("record");
        Map<String, Object> draftJson = json.map(String.valueOf(draft.get("draft_json")));
        List<Object> tags = draftJson.get("tags") instanceof List<?> items ? new ArrayList<>(items) : List.of();
        String finalText = String.valueOf(draft.get("preview_text"));
        LocalDateTime now = LocalDateTime.now();
        jdbcTemplate.update(
                """
                INSERT INTO DAILY_RECORD (id, user_id, session_id, final_draft_id, record_date, final_text, ai_summary, ai_score, tags_json, status, client_confirm_id, third_session_id, request_id, confirmed_at, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, CAST(? AS JSON), ?, ?, ?, ?, ?, ?)
                """,
                id,
                session.get("user_id"),
                session.get("id"),
                draft.get("id"),
                session.get("record_date"),
                finalText,
                String.valueOf(draftJson.getOrDefault("summary", finalText)),
                intValue(draftJson.get("score"), 80),
                json.stringify(tags),
                status,
                clientConfirmId,
                thirdSessionId,
                requestId,
                Timestamp.valueOf(now),
                Timestamp.valueOf(now)
        );
        return queryOne("SELECT * FROM DAILY_RECORD WHERE id = ?", id);
    }

    // 这个函数创建飞书同步记录。
    public Map<String, Object> insertFeishuSync(String recordId, String configId, String thirdSessionId, String requestId, String syncStatus, String errorMessage, int retryCount, Map<String, Object> payload) {
        String id = Ids.newId("sync");
        jdbcTemplate.update(
                """
                INSERT INTO FEISHU_SYNC (id, record_id, config_id, target_type, target_id, payload_json, feishu_ref_id, sync_status, error_message, retry_count, third_session_id, request_id, last_sync_at, created_at)
                VALUES (?, ?, ?, 'bitable', NULL, CAST(? AS JSON), ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                id,
                recordId,
                configId,
                json.stringify(payload),
                payload.get("feishuRefId"),
                syncStatus,
                errorMessage,
                retryCount,
                thirdSessionId,
                requestId,
                Timestamp.valueOf(LocalDateTime.now()),
                Timestamp.valueOf(LocalDateTime.now())
        );
        return queryOne("SELECT * FROM FEISHU_SYNC WHERE id = ?", id);
    }

    // 这个函数更新一次飞书同步尝试的最终状态。
    public Map<String, Object> updateFeishuSync(String syncId, String syncStatus, String errorMessage, Map<String, Object> payload) {
        jdbcTemplate.update(
                """
                UPDATE FEISHU_SYNC
                SET payload_json = CAST(? AS JSON),
                    feishu_ref_id = ?,
                    sync_status = ?,
                    error_message = ?,
                    last_sync_at = ?
                WHERE id = ?
                """,
                json.stringify(payload),
                payload.get("feishuRefId"),
                syncStatus,
                errorMessage,
                Timestamp.valueOf(LocalDateTime.now()),
                syncId
        );
        return queryOne("SELECT * FROM FEISHU_SYNC WHERE id = ?", syncId);
    }

    // 这个函数更新正式记录状态。
    public Map<String, Object> updateDailyRecordStatus(String recordId, String status) {
        jdbcTemplate.update("UPDATE DAILY_RECORD SET status = ? WHERE id = ?", status, recordId);
        return record(recordId);
    }

    // 这个函数写入或更新用户端展示数据。
    public Map<String, Object> upsertDisplay(String recordId, String title, String summary, int score, String displayStatus, Map<String, Object> adminContent, Map<String, Object> displayJson) {
        Map<String, Object> existing = queryOne("SELECT * FROM RECORD_DISPLAY WHERE record_id = ?", recordId);
        if (existing.isEmpty()) {
            jdbcTemplate.update(
                    """
                    INSERT INTO RECORD_DISPLAY (id, record_id, title, summary, score, display_status, admin_content_json, display_json, updated_at)
                    VALUES (?, ?, ?, ?, ?, ?, CAST(? AS JSON), CAST(? AS JSON), ?)
                    """,
                    Ids.newId("display"),
                    recordId,
                    title,
                    summary,
                    score,
                    displayStatus,
                    json.stringify(adminContent),
                    json.stringify(displayJson),
                    Timestamp.valueOf(LocalDateTime.now())
            );
        } else {
            jdbcTemplate.update(
                    """
                    UPDATE RECORD_DISPLAY
                    SET title = ?, summary = ?, score = ?, display_status = ?, admin_content_json = CAST(? AS JSON), display_json = CAST(? AS JSON), updated_at = ?
                    WHERE record_id = ?
                    """,
                    title,
                    summary,
                    score,
                    displayStatus,
                    json.stringify(adminContent),
                    json.stringify(displayJson),
                    Timestamp.valueOf(LocalDateTime.now()),
                    recordId
            );
        }
        return queryOne("SELECT * FROM RECORD_DISPLAY WHERE record_id = ?", recordId);
    }

    // 这个函数把会话标记为 confirmed。
    public void markSessionConfirmed(String sessionId) {
        jdbcTemplate.update("UPDATE RECORD_SESSION SET status = 'confirmed', updated_at = ? WHERE id = ?", Timestamp.valueOf(LocalDateTime.now()), sessionId);
    }

    // 这个函数取消记录会话。
    public Map<String, Object> cancelSession(String sessionId) {
        jdbcTemplate.update("UPDATE RECORD_SESSION SET status = 'cancelled', updated_at = ? WHERE id = ?", Timestamp.valueOf(LocalDateTime.now()), sessionId);
        return requireSession(sessionId);
    }

    // 这个函数统计后台首页数据。
    public Map<String, Object> dashboard(LocalDate date) {
        Integer today = jdbcTemplate.queryForObject("SELECT COUNT(*) FROM DAILY_RECORD WHERE record_date = ?", Integer.class, Date.valueOf(date));
        Integer abnormal = jdbcTemplate.queryForObject("SELECT COUNT(*) FROM DAILY_RECORD WHERE status IN ('sync_failed', 'blocked')", Integer.class);
        Integer pending = jdbcTemplate.queryForObject("SELECT COUNT(*) FROM RECORD_DISPLAY WHERE JSON_LENGTH(admin_content_json) = 0", Integer.class);
        return Map.of("date", date.toString(), "todayRecordCount", safe(today), "pendingFeedbackCount", safe(pending), "abnormalCount", safe(abnormal));
    }

    // 这个函数分页查询后台记录列表。
    public List<Map<String, Object>> adminRecords(LocalDate date, String status, boolean onlyAbnormal, int page, int pageSize) {
        StringBuilder sql = new StringBuilder(
                """
                SELECT dr.id AS record_id, dr.record_date, rd.summary, dr.status, rd.score,
                       fs.sync_status AS feishu_sync_status, fs.retry_count, rd.updated_at
                FROM DAILY_RECORD dr
                LEFT JOIN RECORD_DISPLAY rd ON rd.record_id = dr.id
                LEFT JOIN FEISHU_SYNC fs ON fs.id = (SELECT id FROM FEISHU_SYNC WHERE record_id = dr.id ORDER BY created_at DESC LIMIT 1)
                WHERE 1=1
                """
        );
        List<Object> params = new ArrayList<>();
        if (date != null) {
            sql.append(" AND dr.record_date = ?");
            params.add(Date.valueOf(date));
        }
        if (status != null && !status.isBlank()) {
            sql.append(" AND dr.status = ?");
            params.add(status);
        }
        if (onlyAbnormal) {
            sql.append(" AND dr.status IN ('sync_failed', 'blocked')");
        }
        sql.append(" ORDER BY dr.record_date DESC, dr.created_at DESC LIMIT ? OFFSET ?");
        params.add(pageSize);
        params.add(Math.max(0, page - 1) * pageSize);
        return jdbcTemplate.queryForList(sql.toString(), params.toArray());
    }

    // 这个函数查询后台记录列表总数。
    public int adminRecordCount(LocalDate date, String status, boolean onlyAbnormal) {
        StringBuilder sql = new StringBuilder("SELECT COUNT(*) FROM DAILY_RECORD WHERE 1=1");
        List<Object> params = new ArrayList<>();
        if (date != null) {
            sql.append(" AND record_date = ?");
            params.add(Date.valueOf(date));
        }
        if (status != null && !status.isBlank()) {
            sql.append(" AND status = ?");
            params.add(status);
        }
        if (onlyAbnormal) {
            sql.append(" AND status IN ('sync_failed', 'blocked')");
        }
        Integer count = jdbcTemplate.queryForObject(sql.toString(), Integer.class, params.toArray());
        return safe(count);
    }

    // 这个函数读取正式记录。
    public Map<String, Object> record(String recordId) {
        return queryOne("SELECT * FROM DAILY_RECORD WHERE id = ?", recordId);
    }

    // 这个函数读取正式记录关联草稿。
    public Map<String, Object> draft(String draftId) {
        return queryOne("SELECT * FROM RECORD_DRAFT WHERE id = ?", draftId);
    }

    // 这个函数读取展示记录。
    public Map<String, Object> display(String recordId) {
        return queryOne("SELECT * FROM RECORD_DISPLAY WHERE record_id = ?", recordId);
    }

    // 这个函数读取最新飞书同步记录。
    public Map<String, Object> latestFeishuSync(String recordId) {
        return queryOne("SELECT * FROM FEISHU_SYNC WHERE record_id = ? ORDER BY created_at DESC LIMIT 1", recordId);
    }

    // 这个函数读取单次飞书同步记录。
    public Map<String, Object> feishuSync(String syncId) {
        return queryOne("SELECT * FROM FEISHU_SYNC WHERE id = ?", syncId);
    }

    // 这个函数列出正式记录所有飞书同步记录。
    public List<Map<String, Object>> feishuSyncs(String recordId) {
        return jdbcTemplate.queryForList("SELECT * FROM FEISHU_SYNC WHERE record_id = ? ORDER BY created_at ASC", recordId);
    }

    // 这个函数保存每日内容配置。
    public void saveDailyContent(String targetUserId, String adminId, LocalDate date, List<Map<String, Object>> contents) {
        for (Map<String, Object> item : contents) {
            String contentType = String.valueOf(item.get("contentType"));
            String displayArea = String.valueOf(item.get("displayArea"));
            Map<String, Object> content = item.get("content") instanceof Map<?, ?> map ? castMap(map) : Map.of();
            jdbcTemplate.update(
                    """
                    INSERT INTO DAILY_CONTENT (id, target_user_id, created_by, content_date, content_type, display_area, content_json, resource_id, enabled, created_at, updated_at)
                    VALUES (?, ?, ?, ?, ?, ?, CAST(? AS JSON), ?, ?, ?, ?)
                    ON DUPLICATE KEY UPDATE content_json = VALUES(content_json), resource_id = VALUES(resource_id), enabled = VALUES(enabled), updated_at = VALUES(updated_at)
                    """,
                    Ids.newId("content"),
                    targetUserId,
                    adminId,
                    Date.valueOf(date),
                    contentType,
                    displayArea,
                    json.stringify(content),
                    item.get("resourceId"),
                    Boolean.TRUE.equals(item.get("enabled")) || item.get("enabled") == null,
                    Timestamp.valueOf(LocalDateTime.now()),
                    Timestamp.valueOf(LocalDateTime.now())
            );
        }
    }

    // 这个函数查询单条 SQL，查不到时返回空 Map。
    private Map<String, Object> queryOne(String sql, Object... args) {
        try {
            return new LinkedHashMap<>(jdbcTemplate.queryForMap(sql, args));
        } catch (EmptyResultDataAccessException exception) {
            return Map.of();
        }
    }

    // 这个函数计算下一条消息序号。
    private int nextMessageSequence(String sessionId) {
        Integer value = jdbcTemplate.queryForObject("SELECT COALESCE(MAX(sequence_no), 0) + 1 FROM RECORD_MESSAGE WHERE session_id = ?", Integer.class, sessionId);
        return value == null ? 1 : value;
    }

    // 这个函数计算下一版草稿版本号。
    private int nextDraftVersion(String sessionId) {
        Integer value = jdbcTemplate.queryForObject("SELECT COALESCE(MAX(version_no), 0) + 1 FROM RECORD_DRAFT WHERE session_id = ?", Integer.class, sessionId);
        return value == null ? 1 : value;
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

    // 这个函数把空 Integer 转换为 0。
    private int safe(Integer value) {
        return value == null ? 0 : value;
    }

    // 这个函数把通配 Map 转成字符串键 Map。
    private Map<String, Object> castMap(Map<?, ?> source) {
        Map<String, Object> result = new LinkedHashMap<>();
        source.forEach((key, value) -> result.put(String.valueOf(key), value));
        return result;
    }
}
