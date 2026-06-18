package com.formygirl.admin;

import com.formygirl.auth.AuthService;
import com.formygirl.auth.CurrentPerson;
import com.formygirl.common.ApiResponse;
import com.formygirl.common.RequestIds;
import com.formygirl.trace.TraceService;
import jakarta.servlet.http.HttpServletRequest;
import java.time.LocalDate;
import java.util.List;
import java.util.Map;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.PatchMapping;
import org.springframework.web.bind.annotation.PathVariable;
import org.springframework.web.bind.annotation.PostMapping;
import org.springframework.web.bind.annotation.PutMapping;
import org.springframework.web.bind.annotation.RequestBody;
import org.springframework.web.bind.annotation.RequestHeader;
import org.springframework.web.bind.annotation.RequestParam;
import org.springframework.web.bind.annotation.RestController;

@RestController
public class AdminController {
    private final AuthService authService;
    private final AdminService adminService;
    private final TraceService traceService;

    public AdminController(AuthService authService, AdminService adminService, TraceService traceService) {
        this.authService = authService;
        this.adminService = adminService;
        this.traceService = traceService;
    }

    // 这个接口返回管理员首页统计。
    @GetMapping("/api/admin/dashboard")
    public ApiResponse<Map<String, Object>> dashboard(@RequestHeader("Authorization") String authorization, @RequestParam(required = false) LocalDate date, HttpServletRequest request) {
        authService.requireAdmin(authorization);
        return ApiResponse.ok(adminService.dashboard(date == null ? LocalDate.now() : date), requestId(request));
    }

    // 这个接口返回管理员记录列表。
    @GetMapping("/api/admin/records")
    public ApiResponse<Map<String, Object>> records(
            @RequestHeader("Authorization") String authorization,
            @RequestParam(required = false) LocalDate date,
            @RequestParam(required = false) String status,
            @RequestParam(defaultValue = "false") boolean onlyAbnormal,
            @RequestParam(defaultValue = "1") int page,
            @RequestParam(defaultValue = "20") int pageSize,
            HttpServletRequest request
    ) {
        authService.requireAdmin(authorization);
        return ApiResponse.ok(adminService.records(date, status, onlyAbnormal, page, pageSize), requestId(request));
    }

    // 这个接口返回管理员记录详情。
    @GetMapping("/api/admin/records/{recordId}")
    public ApiResponse<Map<String, Object>> recordDetail(@RequestHeader("Authorization") String authorization, @PathVariable String recordId, HttpServletRequest request) {
        authService.requireAdmin(authorization);
        return ApiResponse.ok(adminService.recordDetail(recordId), requestId(request));
    }

    // 这个接口查询每日内容配置。
    @GetMapping("/api/admin/daily-contents")
    public ApiResponse<Map<String, Object>> dailyContents(@RequestHeader("Authorization") String authorization, @RequestParam String targetUserId, @RequestParam LocalDate date, HttpServletRequest request) {
        authService.requireAdmin(authorization);
        return ApiResponse.ok(adminService.dailyContents(targetUserId, date), requestId(request));
    }

    // 这个接口保存每日内容配置。
    @PutMapping("/api/admin/daily-contents")
    public ApiResponse<Map<String, Object>> saveDailyContents(@RequestHeader("Authorization") String authorization, @RequestBody SaveDailyContentRequest body, HttpServletRequest request) {
        CurrentPerson admin = authService.requireAdmin(authorization);
        return ApiResponse.ok(adminService.saveDailyContents(admin.id(), body.targetUserId(), body.date(), body.contents()), requestId(request));
    }

    // 这个接口重试飞书同步。
    @PostMapping("/api/admin/records/{recordId}/retry-sync")
    public ApiResponse<Map<String, Object>> retrySync(@RequestHeader("Authorization") String authorization, @PathVariable String recordId, @RequestBody RetryRequest body, HttpServletRequest request) {
        authService.requireAdmin(authorization);
        return ApiResponse.ok(adminService.retrySync(recordId, body.mode() == null ? "reuse_payload" : body.mode(), requestId(request)), requestId(request));
    }

    // 这个接口更新用户端展示数据。
    @PatchMapping("/api/admin/records/{recordId}/display")
    public ApiResponse<Map<String, Object>> updateDisplay(@RequestHeader("Authorization") String authorization, @PathVariable String recordId, @RequestBody Map<String, Object> body, HttpServletRequest request) {
        authService.requireAdmin(authorization);
        return ApiResponse.ok(adminService.updateDisplay(recordId, body), requestId(request));
    }

    // 这个接口按条件聚合记录追踪。
    @GetMapping("/api/admin/record-traces")
    public ApiResponse<Map<String, Object>> trace(
            @RequestHeader("Authorization") String authorization,
            @RequestParam(required = false) String sessionId,
            @RequestParam(required = false) String recordId,
            @RequestParam(required = false) String thirdSessionId,
            HttpServletRequest request
    ) {
        authService.requireAdmin(authorization);
        return ApiResponse.ok(traceService.trace(sessionId, recordId, thirdSessionId), requestId(request));
    }

    // 这个接口按会话 ID 查询记录追踪。
    @GetMapping("/api/admin/record-sessions/{sessionId}/trace")
    public ApiResponse<Map<String, Object>> sessionTrace(@RequestHeader("Authorization") String authorization, @PathVariable String sessionId, HttpServletRequest request) {
        authService.requireAdmin(authorization);
        return ApiResponse.ok(traceService.trace(sessionId, null, null), requestId(request));
    }

    // 这个接口按正式记录 ID 查询记录追踪。
    @GetMapping("/api/admin/records/{recordId}/trace")
    public ApiResponse<Map<String, Object>> recordTrace(@RequestHeader("Authorization") String authorization, @PathVariable String recordId, HttpServletRequest request) {
        authService.requireAdmin(authorization);
        return ApiResponse.ok(traceService.trace(null, recordId, null), requestId(request));
    }

    private String requestId(HttpServletRequest request) {
        return String.valueOf(request.getAttribute(RequestIds.ATTRIBUTE));
    }

    public record SaveDailyContentRequest(String targetUserId, LocalDate date, List<Map<String, Object>> contents) {
    }

    public record RetryRequest(String mode) {
    }
}
