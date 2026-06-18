package com.formygirl.record;

import com.formygirl.auth.AuthService;
import com.formygirl.auth.CurrentPerson;
import com.formygirl.common.ApiResponse;
import com.formygirl.common.RequestIds;
import jakarta.servlet.http.HttpServletRequest;
import jakarta.validation.Valid;
import jakarta.validation.constraints.NotBlank;
import java.time.LocalDate;
import java.util.Map;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.PathVariable;
import org.springframework.web.bind.annotation.PostMapping;
import org.springframework.web.bind.annotation.RequestBody;
import org.springframework.web.bind.annotation.RequestHeader;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RequestParam;
import org.springframework.web.bind.annotation.RestController;

@RestController
public class RecordController {
    private final AuthService authService;
    private final RecordService recordService;

    public RecordController(AuthService authService, RecordService recordService) {
        this.authService = authService;
        this.recordService = recordService;
    }

    // 这个接口返回用户首页所需数据。
    @GetMapping("/api/user/home")
    public ApiResponse<Map<String, Object>> home(@RequestHeader("Authorization") String authorization, @RequestParam(required = false) LocalDate date, HttpServletRequest request) {
        CurrentPerson person = authService.requirePerson(authorization);
        return ApiResponse.ok(recordService.home(person, date == null ? LocalDate.now() : date), requestId(request));
    }

    // 这个接口返回用户最近记录列表。
    @GetMapping("/api/user/records")
    public ApiResponse<Map<String, Object>> records(
            @RequestHeader("Authorization") String authorization,
            @RequestParam(required = false) LocalDate fromDate,
            @RequestParam(required = false) LocalDate toDate,
            @RequestParam(defaultValue = "1") int page,
            @RequestParam(defaultValue = "20") int pageSize,
            HttpServletRequest request
    ) {
        CurrentPerson person = authService.requirePerson(authorization);
        LocalDate end = toDate == null ? LocalDate.now() : toDate;
        LocalDate start = fromDate == null ? end.minusDays(30) : fromDate;
        return ApiResponse.ok(recordService.userRecords(person, start, end, page, pageSize), requestId(request));
    }

    // 这个接口创建记录会话。
    @PostMapping("/api/record-sessions")
    public ApiResponse<Map<String, Object>> createSession(@RequestHeader("Authorization") String authorization, @RequestBody CreateSessionRequest body, HttpServletRequest request) {
        CurrentPerson person = authService.requirePerson(authorization);
        LocalDate recordDate = body.recordDate() == null ? LocalDate.now() : body.recordDate();
        return ApiResponse.created(recordService.createSession(person, recordDate, requestId(request)), requestId(request));
    }

    // 这个接口发送文本消息或修改指令。
    @PostMapping("/api/record-sessions/{sessionId}/messages")
    public ApiResponse<Map<String, Object>> sendMessage(@RequestHeader("Authorization") String authorization, @PathVariable String sessionId, @Valid @RequestBody SendMessageRequest body, HttpServletRequest request) {
        CurrentPerson person = authService.requirePerson(authorization);
        return ApiResponse.ok(recordService.sendMessage(person, sessionId, body.clientMessageId(), body.content(), requestId(request)), requestId(request));
    }

    // 这个接口查询记录会话详情。
    @GetMapping("/api/record-sessions/{sessionId}")
    public ApiResponse<Map<String, Object>> session(@RequestHeader("Authorization") String authorization, @PathVariable String sessionId, HttpServletRequest request) {
        authService.requirePerson(authorization);
        return ApiResponse.ok(recordService.sessionDetail(sessionId), requestId(request));
    }

    // 这个接口确认写入记录。
    @PostMapping("/api/record-sessions/{sessionId}/confirm")
    public ApiResponse<Map<String, Object>> confirm(@RequestHeader("Authorization") String authorization, @PathVariable String sessionId, @Valid @RequestBody ConfirmRequest body, HttpServletRequest request) {
        CurrentPerson person = authService.requirePerson(authorization);
        return ApiResponse.ok(recordService.confirm(person, sessionId, body.draftId(), body.clientConfirmId(), requestId(request)), requestId(request));
    }

    // 这个接口取消记录会话。
    @PostMapping("/api/record-sessions/{sessionId}/cancel")
    public ApiResponse<Map<String, Object>> cancel(@RequestHeader("Authorization") String authorization, @PathVariable String sessionId, HttpServletRequest request) {
        CurrentPerson person = authService.requirePerson(authorization);
        return ApiResponse.ok(recordService.cancel(person, sessionId), requestId(request));
    }

    private String requestId(HttpServletRequest request) {
        return String.valueOf(request.getAttribute(RequestIds.ATTRIBUTE));
    }

    public record CreateSessionRequest(LocalDate recordDate, String source) {
    }

    public record SendMessageRequest(@NotBlank String clientMessageId, @NotBlank String content) {
    }

    public record ConfirmRequest(@NotBlank String clientConfirmId, @NotBlank String draftId) {
    }
}
