package com.formygirl.record;

import com.formygirl.common.ApiException;
import com.formygirl.common.JsonSupport;
import com.formygirl.comment.CommentRepository;
import com.formygirl.comment.CommentService;
import com.formygirl.feishu.FeishuConfigService;
import com.formygirl.identity.CurrentPerson;
import com.formygirl.persistence.BusinessRepository;
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
    private final FeishuConfigService feishuConfigService;
    private final JsonSupport json;
    private final CommentRepository commentRepository;
    private final CommentService commentService;

    public RecordService(BusinessRepository repository, ThirdWorkflowClient thirdClient, FeishuConfigService feishuConfigService, JsonSupport json, CommentRepository commentRepository, CommentService commentService) {
        this.repository = repository;
        this.thirdClient = thirdClient;
        this.feishuConfigService = feishuConfigService;
        this.json = json;
        this.commentRepository = commentRepository;
        this.commentService = commentService;
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
        return recordsForOwner(person.id(), fromDate, toDate, page, pageSize);
    }

    // 这个函数组装指定用户的最近记录列表并附带绑定评论。
    public Map<String, Object> recordsForOwner(String ownerUserId, LocalDate fromDate, LocalDate toDate, int page, int pageSize) {
        List<Map<String, Object>> rows = repository.userRecords(ownerUserId, fromDate, toDate, page, pageSize);
        return Map.of(
                "items", rows.stream().map(this::displayWithCommentDto).toList(),
                "page", page,
                "pageSize", pageSize,
                "total", repository.userRecordCount(ownerUserId, fromDate, toDate)
        );
    }

    // 这个函数创建记录会话。
    @Transactional
    public Map<String, Object> createSession(CurrentPerson person, LocalDate recordDate, String requestId, String feishuTableConfigId) {
        String resolvedTableConfigId = feishuConfigService.resolveTableConfigIdForNewSession(person.id(), feishuTableConfigId);
        return sessionDto(repository.createSession(person.id(), recordDate, requestId, resolvedTableConfigId));
    }

    // 这个函数处理文本输入或修改指令，并让 third 自行决定 workflow。
    @Transactional
    public Map<String, Object> sendMessage(CurrentPerson person, String sessionId, String clientMessageId, String content, String requestId) {
        Map<String, Object> session = requireOwnedSession(person, sessionId);
        Map<String, Object> existing = repository.findMessageByClientId(sessionId, clientMessageId);
        if (!existing.isEmpty()) {
            return sessionDetail(sessionId);
        }
        Map<String, Object> userMessage = repository.insertMessage(sessionId, "user", "text", content, null, clientMessageId, null, requestId);
        FeishuConfigService.WorkflowFeishuContext feishuContext = feishuContext(person.id(), session);
        Map<String, Object> third = thirdClient.invoke(content, workflowMetadata(feishuContext, Map.of(
                "businessSessionId", sessionId,
                "idempotencyKey", clientMessageId
        )), feishuContext.privateMetadata());
        String thirdSessionId = stringOrNull(third.get("session_id"));
        userMessage = repository.updateMessageThirdSession(String.valueOf(userMessage.get("id")), thirdSessionId);
        Map<String, Object> task = repository.createWorkflowTask(sessionId, "message", clientMessageId, String.valueOf(userMessage.get("id")), null, thirdSessionId, null, null, "submitted", requestId);
        return processingResult(sessionId, userMessage, task);
    }

    // 这个函数查询记录会话详情。
    public Map<String, Object> sessionDetail(CurrentPerson person, String sessionId) {
        requireOwnedSession(person, sessionId);
        return sessionDetail(sessionId);
    }

    // 这个函数查询记录会话详情。
    public Map<String, Object> sessionDetail(String sessionId) {
        Map<String, Object> session = repository.requireSession(sessionId);
        if (session.isEmpty()) {
            throw new ApiException(HttpStatus.NOT_FOUND, "NOT_FOUND", "记录会话不存在");
        }
        Map<String, Object> currentDraft = repository.currentDraft(sessionId);
        Map<String, Object> task = repository.latestWorkflowTask(sessionId);
        Map<String, Object> record = repository.findRecordBySession(sessionId);
        return dto(
                "session", sessionDto(session),
                "messages", repository.sessionMessages(sessionId).stream().map(this::messageDto).toList(),
                "currentDraft", currentDraft.isEmpty() ? null : draftDto(currentDraft),
                "pendingConfirmation", pendingConfirmationFromTask(task),
                "latestWorkflowTask", task.isEmpty() ? null : workflowTaskDto(task),
                "record", record.isEmpty() ? null : recordDto(record),
                "pollAfterMs", 1500
        );
    }

    // 这个函数确认草稿并请求 third 生成写入确认。
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
        Map<String, Object> third = invokeConfirmWorkflow(session, draft, clientConfirmId);
        String thirdSessionId = stringOrNull(third.get("session_id"));
        Map<String, Object> task = repository.createWorkflowTask(sessionId, "confirm", clientConfirmId, null, draftId, thirdSessionId, null, true, "submitted", requestId);
        return processingConfirmResult(sessionId, draft, task);
    }

    // 这个函数处理用户对 third 写入确认预览的最终选择。
    @Transactional
    public Map<String, Object> resumeConfirm(CurrentPerson person, String sessionId, String draftId, String clientConfirmId, String thirdSessionId, String confirmationId, boolean approved, String requestId) {
        requireOwnedSession(person, sessionId);
        String resolvedConfirmId = clientConfirmId == null || clientConfirmId.isBlank() ? thirdSessionId + "_confirm" : clientConfirmId;
        Map<String, Object> existing = repository.findRecordByConfirmId(sessionId, resolvedConfirmId);
        if (!existing.isEmpty()) {
            return confirmResult(existing);
        }
        Map<String, Object> draft = draftId == null || draftId.isBlank() ? Map.of() : repository.draft(draftId);
        if (!draft.isEmpty() && !sessionId.equals(String.valueOf(draft.get("session_id")))) {
            throw new ApiException(HttpStatus.NOT_FOUND, "NOT_FOUND", "草稿不存在");
        }
        if (!approved) {
            thirdClient.resume(thirdSessionId, confirmationId, "业务前端取消写入", false);
            Map<String, Object> task = repository.createWorkflowTask(sessionId, "resume", resolvedConfirmId, null, draftId, thirdSessionId, confirmationId, false, "cancelled", requestId);
            Map<String, Object> reopened = draft.isEmpty() ? Map.of() : repository.reopenDraft(sessionId, draftId);
            Map<String, Object> reply = repository.insertMessage(sessionId, "system", "text", "已取消写入，可以继续修改。", null, null, thirdSessionId, requestId);
            return dto(
                    "status", "cancelled",
                    "workflowStatus", "cancelled",
                    "latestWorkflowTask", workflowTaskDto(task),
                    "session", sessionDto(repository.requireSession(sessionId)),
                    "draft", reopened.isEmpty() ? null : draftDto(reopened),
                    "replyMessage", messageDto(reply)
            );
        }
        thirdClient.resume(thirdSessionId, confirmationId, "业务前端已确认写入", true);
        Map<String, Object> task = repository.createWorkflowTask(sessionId, "resume", resolvedConfirmId, null, draftId, thirdSessionId, confirmationId, true, "submitted", requestId);
        return processingConfirmResult(sessionId, draft, task);
    }

    // 这个函数把 third 终态落成本地正式记录、同步记录和展示记录。
    private Map<String, Object> completeConfirm(Map<String, Object> session, Map<String, Object> draft, String clientConfirmId, Map<String, Object> third, String requestId) {
        String sessionId = String.valueOf(session.get("id"));
        String thirdStatus = String.valueOf(third.get("status"));
        Object thirdSessionValue = third.get("session_id");
        String thirdSessionId = thirdSessionValue == null ? null : String.valueOf(thirdSessionValue);
        String recordStatus = "success".equals(thirdStatus) ? "success" : "sync_failed";
        String errorMessage = "success".equals(thirdStatus) ? null : String.valueOf(third.getOrDefault("error_text", "third workflow 未成功完成"));
        Map<String, Object> record = repository.insertDailyRecord(session, draft, clientConfirmId, thirdSessionId, requestId, recordStatus);
        Map<String, Object> draftJson = json.map(String.valueOf(draft.get("draft_json")));
        Map<String, Object> syncPayload = dto("thirdStatus", thirdStatus, "thirdSessionId", thirdSessionId);
        if (thirdSessionId != null && !thirdSessionId.isBlank()) {
            syncPayload.put("thirdSnapshot", safeSnapshot(thirdSessionId));
        }
        String configId = stringOrNull(session.get("feishu_table_config_id"));
        Map<String, Object> sync = repository.insertFeishuSync(String.valueOf(record.get("id")), configId, thirdSessionId, requestId, "success".equals(recordStatus) ? "success" : "failed", errorMessage, "success".equals(recordStatus) ? 0 : 1, syncPayload);
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
        return dto("session", sessionDto(repository.requireSession(sessionId)), "record", recordDto(record), "feishuSync", syncDto(sync), "display", displayDto(display), "replyMessage", messageDto(reply), "thirdStatus", thirdStatus);
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

    // 这个函数由后台调度器批量推进 third workflow 跟踪任务。
    public void processPendingWorkflowTasks() {
        for (Map<String, Object> task : repository.pendingWorkflowTasks(10)) {
            processWorkflowTask(task);
        }
    }

    // 这个函数查询 third 状态，并在终态或确认态时把结果落到业务表。
    public void processWorkflowTask(Map<String, Object> task) {
        String taskId = String.valueOf(task.get("id"));
        String sessionId = String.valueOf(task.get("session_id"));
        Map<String, Object> session = repository.requireSession(sessionId);
        if (session.isEmpty()) {
            repository.updateWorkflowTaskStatus(taskId, "failed", "记录会话不存在");
            return;
        }
        if ("cancelled".equals(String.valueOf(session.get("status")))) {
            repository.updateWorkflowTaskStatus(taskId, "cancelled", "记录会话已取消");
            return;
        }
        String thirdSessionId = stringOrNull(task.get("third_session_id"));
        if (thirdSessionId == null) {
            repository.updateWorkflowTaskStatus(taskId, "failed", "third_session_id 为空");
            return;
        }
        try {
            Map<String, Object> third = thirdClient.get(thirdSessionId);
            String status = String.valueOf(third.get("status"));
            if ("queued".equals(status) || "running".equals(status)) {
                repository.updateWorkflowTaskStatus(taskId, "running", null);
                return;
            }
            if (isWaitingUser(third)) {
                applyWaitingUserTask(task, third);
                return;
            }
            if (isWorkflowTerminal(third)) {
                applyTerminalTask(task, third);
                return;
            }
            repository.updateWorkflowTaskStatus(taskId, "running", null);
        } catch (Exception exception) {
            repository.updateWorkflowTaskStatus(taskId, "failed", exception.getMessage());
        }
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

    // 这个函数返回已提交 third、等待前端轮询的消息结果。
    private Map<String, Object> processingResult(String sessionId, Map<String, Object> userMessage, Map<String, Object> task) {
        return dto(
                "session", sessionDto(repository.requireSession(sessionId)),
                "userMessage", messageDto(userMessage),
                "workflowStatus", "processing",
                "latestWorkflowTask", workflowTaskDto(task),
                "pollAfterMs", 1500
        );
    }

    // 这个函数返回已提交 third、等待后台完成确认链路的结果。
    private Map<String, Object> processingConfirmResult(String sessionId, Map<String, Object> draft, Map<String, Object> task) {
        return dto(
                "session", sessionDto(repository.requireSession(sessionId)),
                "draft", draft.isEmpty() ? null : draftDto(draft),
                "workflowStatus", "processing",
                "latestWorkflowTask", workflowTaskDto(task),
                "pollAfterMs", 1500
        );
    }

    // 这个函数根据最近的 workflow task 构造前端待确认卡片。
    private Map<String, Object> pendingConfirmationFromTask(Map<String, Object> task) {
        if (task == null || task.isEmpty() || !"waiting_user".equals(String.valueOf(task.get("status")))) {
            return null;
        }
        String thirdSessionId = stringOrNull(task.get("third_session_id"));
        Map<String, Object> snapshot = safeSnapshot(thirdSessionId);
        Map<String, Object> confirmation = mapValue(snapshot.get("confirmation"));
        Object preview = selectedConfirmationPreview(snapshot, confirmation.get("previewJson"));
        return dto(
                "status", "waiting_user",
                "thirdSessionId", thirdSessionId,
                "confirmationId", firstMappedValue(confirmation, task.get("confirmation_id"), "confirmationId", "confirmation_id"),
                "requestText", firstMappedValue(confirmation, null, "requestText", "request_text"),
                "preview", preview instanceof Map<?, ?> map ? castMap(map) : Map.of(),
                "clientConfirmId", task.get("client_action_id"),
                "draftId", stringOrNull(task.get("draft_id"))
        );
    }

    // 这个函数把 workflow task 转成前端可轮询的状态对象。
    private Map<String, Object> workflowTaskDto(Map<String, Object> row) {
        if (row == null || row.isEmpty()) {
            return Map.of();
        }
        return dto(
                "id", row.get("id"),
                "sessionId", row.get("session_id"),
                "triggerType", row.get("trigger_type"),
                "clientActionId", row.get("client_action_id"),
                "thirdSessionId", row.get("third_session_id"),
                "confirmationId", row.get("confirmation_id"),
                "approved", row.get("approved"),
                "status", row.get("status"),
                "errorText", row.get("error_text"),
                "createdAt", row.get("created_at"),
                "updatedAt", row.get("updated_at")
        );
    }

    // 这个函数从 third artifact 中提取草稿。
    private Map<String, Object> extractDraft(String thirdSessionId, Map<String, Object> session) {
        if (thirdSessionId == null || thirdSessionId.isBlank()) {
            return Map.of();
        }
        Map<String, Object> draft = snapshotOutput(safeSnapshot(thirdSessionId), "draft");
        if (!draft.isEmpty()) {
            return normalizeDraft(draft, session);
        }
        return Map.of();
    }

    // 这个函数提交确认写入 workflow，不等待 third 执行完成。
    private Map<String, Object> invokeConfirmWorkflow(Map<String, Object> session, Map<String, Object> draft, String clientConfirmId) {
        String sessionId = String.valueOf(session.get("id"));
        Map<String, Object> draftJson = json.map(String.valueOf(draft.get("draft_json")));
        String title = String.valueOf(draftJson.getOrDefault("title", "今日自律记录"));
        String summary = String.valueOf(draftJson.getOrDefault("summary", draft.get("preview_text")));
        FeishuConfigService.WorkflowFeishuContext feishuContext = feishuContext(String.valueOf(session.get("user_id")), session);
        return thirdClient.invoke("新增一条记录，事项名称为" + title + "，总结为" + summary, workflowMetadata(feishuContext, Map.of(
                "businessSessionId", sessionId,
                "operation", "confirm_sync",
                "idempotencyKey", clientConfirmId
        )), feishuContext.privateMetadata());
    }

    // 这个函数把 waiting_user 的 third 状态转换成本地草稿或待确认任务。
    private void applyWaitingUserTask(Map<String, Object> task, Map<String, Object> third) {
        String triggerType = String.valueOf(task.get("trigger_type"));
        String sessionId = String.valueOf(task.get("session_id"));
        String thirdSessionId = stringOrNull(task.get("third_session_id"));
        Map<String, Object> snapshot = safeSnapshot(thirdSessionId);
        String confirmationId = stringOrNull(firstMappedValue(mapValue(snapshot.get("confirmation")), confirmationValue(third, "confirmation_id"), "confirmationId", "confirmation_id"));
        String draftId = stringOrNull(task.get("draft_id"));
        if ("message".equals(triggerType)) {
            Map<String, Object> session = repository.requireSession(sessionId);
            Map<String, Object> message = repository.message(String.valueOf(task.get("source_message_id")));
            Map<String, Object> validationData = snapshotOutput(snapshot, "writePayload");
            Map<String, Object> draftData = shouldCreateLocalDraft(validationData) ? draftFromValidation(validationData, String.valueOf(message.get("content")), session) : Map.of();
            if (!draftData.isEmpty()) {
                repository.replaceActiveDrafts(sessionId);
                Map<String, Object> draft = repository.insertDraft(sessionId, draftData, String.valueOf(draftData.get("previewText")), thirdSessionId, String.valueOf(task.get("request_id")));
                draftId = String.valueOf(draft.get("id"));
            }
            repository.insertMessage(sessionId, "ai", "text", "third 已生成需要确认的操作，请核对后决定是否执行。", null, null, thirdSessionId, String.valueOf(task.get("request_id")));
        } else if ("confirm".equals(triggerType)) {
            repository.insertMessage(sessionId, "system", "text", "请确认即将写入飞书的内容。", null, null, thirdSessionId, String.valueOf(task.get("request_id")));
        }
        repository.markWorkflowTaskWaitingUser(String.valueOf(task.get("id")), confirmationId, draftId);
    }

    // 这个函数把 third 终态转换成业务草稿、正式记录或错误消息。
    private void applyTerminalTask(Map<String, Object> task, Map<String, Object> third) {
        String triggerType = String.valueOf(task.get("trigger_type"));
        String thirdStatus = String.valueOf(third.get("status"));
        if ("message".equals(triggerType)) {
            applyTerminalMessageTask(task, third, thirdStatus);
            return;
        }
        applyTerminalConfirmTask(task, third);
    }

    // 这个函数处理消息阶段 workflow 的终态。
    private void applyTerminalMessageTask(Map<String, Object> task, Map<String, Object> third, String thirdStatus) {
        String sessionId = String.valueOf(task.get("session_id"));
        String thirdSessionId = stringOrNull(task.get("third_session_id"));
        String requestId = String.valueOf(task.get("request_id"));
        if ("success".equals(thirdStatus)) {
            Map<String, Object> session = repository.requireSession(sessionId);
            Map<String, Object> draftData = extractDraft(thirdSessionId, session);
            if (!draftData.isEmpty()) {
                repository.replaceActiveDrafts(sessionId);
                repository.insertDraft(sessionId, draftData, String.valueOf(draftData.get("previewText")), thirdSessionId, requestId);
                repository.insertMessage(sessionId, "ai", "text", "我整理了一版草稿，你可以直接确认，也可以继续告诉我怎么改。", null, null, thirdSessionId, requestId);
            } else {
                repository.insertMessage(sessionId, "ai", "text", thirdAnswer(third), null, null, thirdSessionId, requestId);
            }
            repository.updateWorkflowTaskStatus(String.valueOf(task.get("id")), "completed", null);
            return;
        }
        String errorText = String.valueOf(third.getOrDefault("error_text", thirdStatus));
        repository.insertMessage(sessionId, "ai", "text", "third workflow 执行失败：" + errorText, null, null, thirdSessionId, requestId);
        repository.updateWorkflowTaskStatus(String.valueOf(task.get("id")), "failed", errorText);
    }

    // 这个函数处理确认或继续确认 workflow 的终态。
    private void applyTerminalConfirmTask(Map<String, Object> task, Map<String, Object> third) {
        String sessionId = String.valueOf(task.get("session_id"));
        String draftId = stringOrNull(task.get("draft_id"));
        String thirdSessionId = stringOrNull(task.get("third_session_id"));
        String requestId = String.valueOf(task.get("request_id"));
        Map<String, Object> draft = draftId == null ? Map.of() : repository.draft(draftId);
        if (draft.isEmpty()) {
            repository.insertMessage(sessionId, "system", "text", thirdAnswer(third), null, null, thirdSessionId, requestId);
            repository.updateWorkflowTaskStatus(String.valueOf(task.get("id")), "completed", null);
            return;
        }
        completeConfirm(repository.requireSession(sessionId), draft, String.valueOf(task.get("client_action_id")), third, requestId);
        repository.updateWorkflowTaskStatus(String.valueOf(task.get("id")), "completed", null);
    }

    // 这个函数判断 third 是否正在等待用户确认。
    private boolean isWaitingUser(Map<String, Object> third) {
        return "waiting_user".equals(String.valueOf(third.get("status")));
    }

    // 这个函数判断 third workflow 是否已经到终态。
    private boolean isWorkflowTerminal(Map<String, Object> third) {
        return List.of("success", "failed", "cancelled").contains(String.valueOf(third.get("status")));
    }

    // 这个函数读取 third response.confirmation 里的兼容字段。
    private Object confirmationValue(Map<String, Object> third, String key) {
        return mapValue(third.get("confirmation")).get(key);
    }

    // 这个函数判断当前 waiting_user 是否可以落成本地记录草稿。
    private boolean shouldCreateLocalDraft(Map<String, Object> validationData) {
        return "create_record".equals(String.valueOf(validationData.get("operation")));
    }

    // 这个函数把 third create_record 的确认预览转换成本地 RECORD_DRAFT。
    private Map<String, Object> draftFromValidation(Map<String, Object> validationData, String content, Map<String, Object> session) {
        Map<String, Object> preview = validationData.get("preview") instanceof Map<?, ?> map ? castMap(map) : Map.of();
        Map<String, Object> fields = firstPreviewFields(preview);
        String summary = firstText(fields, content, "总结", "summary", "内容", "记录", "事项内容");
        String title = firstText(fields, summary.isBlank() ? "今日自律记录" : summary, "事项名称", "标题", "title", "名称");
        if (title.length() > 24) {
            title = title.substring(0, 24);
        }
        return normalizeDraft(
                dto(
                        "title", title,
                        "recordDate", String.valueOf(session.get("record_date")),
                        "summary", summary,
                        "score", scoreFromFields(fields),
                        "tags", List.of("飞书写入"),
                        "suggestion", "已根据 third 的写入预览生成，确认后会继续执行 workflow。",
                        "previewText", summary,
                        "source", "third.validation"
                ),
                session
        );
    }

    // 这个函数补齐 third 草稿 artifact 中可能缺失的前端展示字段。
    private Map<String, Object> normalizeDraft(Map<String, Object> draft, Map<String, Object> session) {
        String summary = textOrDefault(draft.get("summary"), textOrDefault(draft.get("previewText"), "今天的记录已整理完成。"));
        String previewText = textOrDefault(draft.get("previewText"), summary);
        String title = textOrDefault(draft.get("title"), "今日自律记录");
        String recordDate = textOrDefault(draft.get("recordDate"), String.valueOf(session.get("record_date")));
        Object tags = draft.get("tags") instanceof List<?> ? draft.get("tags") : List.of("记录");
        return dto(
                "title", title,
                "recordDate", recordDate,
                "summary", summary,
                "score", intValue(draft.get("score"), 80),
                "tags", tags,
                "suggestion", textOrDefault(draft.get("suggestion"), ""),
                "previewText", previewText,
                "source", textOrDefault(draft.get("source"), "third")
        );
    }

    // 这个函数从确认预览中取第一条记录的 fields。
    private Map<String, Object> firstPreviewFields(Map<String, Object> preview) {
        Object records = preview.get("records");
        if (records instanceof List<?> list && !list.isEmpty() && list.get(0) instanceof Map<?, ?> record) {
            Object fields = record.get("fields");
            if (fields instanceof Map<?, ?> fieldsMap) {
                return castMap(fieldsMap);
            }
        }
        Object fields = preview.get("fields");
        return fields instanceof Map<?, ?> map ? castMap(map) : Map.of();
    }

    // 这个函数安全读取 third snapshot；失败时返回空 Map，不影响前端确认展示。
    private Map<String, Object> safeSnapshot(String thirdSessionId) {
        if (thirdSessionId == null || thirdSessionId.isBlank()) {
            return Map.of();
        }
        try {
            Map<String, Object> snapshot = thirdClient.snapshot(thirdSessionId);
            return snapshot == null ? Map.of() : snapshot;
        } catch (Exception ignored) {
            return Map.of();
        }
    }

    // 这个函数从 snapshot.outputs 里读取指定输出对象。
    private Map<String, Object> snapshotOutput(Map<String, Object> snapshot, String outputKey) {
        Map<String, Object> outputs = mapValue(snapshot.get("outputs"));
        return mapValue(outputs.get(outputKey));
    }

    // 这个函数选择给前端展示的确认预览，优先用后端可控的 writePayload.preview。
    private Object selectedConfirmationPreview(Map<String, Object> snapshot, Object fallback) {
        Map<String, Object> writePayload = snapshotOutput(snapshot, "writePayload");
        Object preview = writePayload.get("preview");
        if (preview instanceof Map<?, ?> map && !map.isEmpty()) {
            return castMap(map);
        }
        Map<String, Object> confirmation = mapValue(snapshot.get("confirmation"));
        Object previewJson = confirmation.get("previewJson");
        if (previewJson instanceof Map<?, ?> map && !map.isEmpty()) {
            return castMap(map);
        }
        return fallback;
    }

    // 这个函数把任意对象安全转换成字符串键 Map。
    private Map<String, Object> mapValue(Object value) {
        return value instanceof Map<?, ?> map ? castMap(map) : Map.of();
    }

    // 这个函数读取多个候选字段中的第一段非空文本。
    private String firstText(Map<String, Object> source, String fallback, String... keys) {
        for (String key : keys) {
            String value = textOrDefault(source.get(key), "");
            if (!value.isBlank()) {
                return value;
            }
        }
        String joined = joinFieldValues(source);
        return joined.isBlank() ? fallback : joined;
    }

    // 这个函数把 fields 中的常见评分字段转换为本地 0-100 分。
    private int scoreFromFields(Map<String, Object> fields) {
        Object score = firstValue(fields, "score", "评分", "得分", "分数");
        if (score != null) {
            return intValue(score, 80);
        }
        String rating = textOrDefault(firstValue(fields, "评级", "等级", "状态"), "").trim().toUpperCase();
        return switch (rating) {
            case "A" -> 95;
            case "B" -> 80;
            case "C" -> 65;
            case "D" -> 45;
            default -> 80;
        };
    }

    // 这个函数读取多个候选字段中的第一个值。
    private Object firstValue(Map<String, Object> source, String... keys) {
        for (String key : keys) {
            Object value = source.get(key);
            if (value != null && !String.valueOf(value).isBlank()) {
                return value;
            }
        }
        return null;
    }

    // 这个函数读取多个候选字段中的第一个值，找不到时返回 fallback。
    private Object firstMappedValue(Map<String, Object> source, Object fallback, String... keys) {
        Object value = firstValue(source, keys);
        return value == null ? fallback : value;
    }

    // 这个函数把字段值拼成一句兜底摘要。
    private String joinFieldValues(Map<String, Object> source) {
        List<String> values = new ArrayList<>();
        for (Object value : source.values()) {
            String text = textOrDefault(value, "");
            if (!text.isBlank()) {
                values.add(text);
            }
        }
        return String.join("，", values);
    }

    // 这个函数提取 third response 中的最终文本。
    private String thirdAnswer(Map<String, Object> third) {
        Object content = third.get("content");
        if (content instanceof List<?> list && !list.isEmpty() && list.get(0) instanceof Map<?, ?> first) {
            String text = textOrDefault(first.get("text"), "");
            if (!text.isBlank()) {
                return text;
            }
        }
        String error = textOrDefault(third.get("error_text"), "");
        if (!error.isBlank()) {
            return error;
        }
        return "third workflow 已完成，状态为 " + third.get("status") + "。";
    }

    // 这个函数读取当前会话绑定的飞书表配置快照。
    private FeishuConfigService.WorkflowFeishuContext feishuContext(String userId, Map<String, Object> session) {
        return feishuConfigService.workflowContext(userId, stringOrNull(session.get("feishu_table_config_id")));
    }

    // 这个函数合并业务 metadata 和可公开的飞书表信息；密钥不会进入这里。
    private Map<String, Object> workflowMetadata(FeishuConfigService.WorkflowFeishuContext feishuContext, Map<String, Object> base) {
        Map<String, Object> metadata = new LinkedHashMap<>(base);
        metadata.putAll(feishuContext.publicMetadata());
        return metadata;
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
        return dto("id", row.get("id"), "status", row.get("status"), "currentDraftId", row.get("current_draft_id"), "feishuTableConfigId", row.get("feishu_table_config_id"), "createdAt", row.get("created_at"), "updatedAt", row.get("updated_at"));
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

    // 这个函数转换带绑定评论的展示记录 DTO。
    private Map<String, Object> displayWithCommentDto(Map<String, Object> row) {
        Map<String, Object> result = new LinkedHashMap<>(displayDto(row));
        Map<String, Object> comment = commentRepository.latestComment(String.valueOf(row.get("record_id")));
        result.put("boundComment", commentService.commentDto(comment));
        result.put("managerComment", comment.get("content"));
        result.put("managerScore", comment.get("score"));
        return result;
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

    // 这个函数把对象转换成字符串，空值使用兜底。
    private String textOrDefault(Object value, String fallback) {
        if (value == null) {
            return fallback;
        }
        String text = String.valueOf(value).trim();
        return text.isBlank() ? fallback : text;
    }

    // 这个函数把对象转换成可空字符串。
    private String stringOrNull(Object value) {
        if (value == null) {
            return null;
        }
        String text = String.valueOf(value);
        return text.isBlank() || "null".equals(text) ? null : text;
    }

    // 这个函数把通配 Map 转成字符串键 Map。
    private Map<String, Object> castMap(Map<?, ?> source) {
        Map<String, Object> result = new LinkedHashMap<>();
        source.forEach((key, value) -> result.put(String.valueOf(key), value));
        return result;
    }
}
