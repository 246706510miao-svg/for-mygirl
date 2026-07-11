package com.formygirl.record.session;

import com.formygirl.common.ApiResponse;
import com.formygirl.common.RequestIds;
import com.formygirl.identity.CurrentPerson;
import com.formygirl.identity.IdentityService;
import com.formygirl.record.RecordService;
import jakarta.servlet.http.HttpServletRequest;
import jakarta.validation.Valid;
import jakarta.validation.constraints.NotBlank;
import java.time.LocalDate;
import java.util.Map;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.PathVariable;
import org.springframework.web.bind.annotation.PostMapping;
import org.springframework.web.bind.annotation.RequestBody;
import org.springframework.web.bind.annotation.RestController;

@RestController
public class RecordSessionController {
    private final IdentityService identityService;
    private final RecordService recordService;

    public RecordSessionController(IdentityService identityService, RecordService recordService) {
        this.identityService = identityService;
        this.recordService = recordService;
    }

    // 这个接口创建记录会话。
    @PostMapping("/api/record-sessions")
    public ApiResponse<Map<String, Object>> createSession(@RequestBody CreateSessionRequest body, HttpServletRequest request) {
        CurrentPerson person = identityService.requirePerson(request);
        LocalDate recordDate = body.recordDate() == null ? LocalDate.now() : body.recordDate();
        return ApiResponse.created(recordService.createSession(person, recordDate, requestId(request), body.feishuTableConfigId()), requestId(request));
    }

    // 这个接口发送文本消息或修改指令。
    @PostMapping("/api/record-sessions/{sessionId}/messages")
    public ApiResponse<Map<String, Object>> sendMessage(@PathVariable String sessionId, @Valid @RequestBody SendMessageRequest body, HttpServletRequest request) {
        CurrentPerson person = identityService.requirePerson(request);
        return ApiResponse.ok(recordService.sendMessage(person, sessionId, body.clientMessageId(), body.content(), requestId(request)), requestId(request));
    }

    // 这个接口查询记录会话详情。
    @GetMapping("/api/record-sessions/{sessionId}")
    public ApiResponse<Map<String, Object>> session(@PathVariable String sessionId, HttpServletRequest request) {
        CurrentPerson person = identityService.requirePerson(request);
        return ApiResponse.ok(recordService.sessionDetail(person, sessionId), requestId(request));
    }

    // 这个接口确认写入记录。
    @PostMapping("/api/record-sessions/{sessionId}/confirm")
    public ApiResponse<Map<String, Object>> confirm(@PathVariable String sessionId, @Valid @RequestBody ConfirmRequest body, HttpServletRequest request) {
        CurrentPerson person = identityService.requirePerson(request);
        return ApiResponse.ok(recordService.confirm(person, sessionId, body.draftId(), body.clientConfirmId(), requestId(request)), requestId(request));
    }

    // 这个接口继续或取消 third 等待中的写入确认。
    @PostMapping("/api/record-sessions/{sessionId}/confirm/resume")
    public ApiResponse<Map<String, Object>> resumeConfirm(@PathVariable String sessionId, @Valid @RequestBody ResumeConfirmRequest body, HttpServletRequest request) {
        CurrentPerson person = identityService.requirePerson(request);
        return ApiResponse.ok(recordService.resumeConfirm(person, sessionId, body.draftId(), body.clientConfirmId(), body.thirdSessionId(), body.confirmationId(), body.response(), body.content(), body.approved(), requestId(request)), requestId(request));
    }

    // 这个接口取消记录会话。
    @PostMapping("/api/record-sessions/{sessionId}/cancel")
    public ApiResponse<Map<String, Object>> cancel(@PathVariable String sessionId, HttpServletRequest request) {
        CurrentPerson person = identityService.requirePerson(request);
        return ApiResponse.ok(recordService.cancel(person, sessionId), requestId(request));
    }

    private String requestId(HttpServletRequest request) {
        return String.valueOf(request.getAttribute(RequestIds.ATTRIBUTE));
    }

    public record CreateSessionRequest(LocalDate recordDate, String source, String feishuTableConfigId) {
    }

    public record SendMessageRequest(@NotBlank String clientMessageId, @NotBlank String content) {
    }

    public record ConfirmRequest(@NotBlank String clientConfirmId, @NotBlank String draftId) {
    }

    public record ResumeConfirmRequest(String clientConfirmId, String draftId, @NotBlank String thirdSessionId, @NotBlank String confirmationId, String response, String content, boolean approved) {
    }
}
