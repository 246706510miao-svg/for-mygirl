package com.formygirl.stats;

import com.formygirl.common.ApiResponse;
import com.formygirl.common.RequestIds;
import com.formygirl.identity.CurrentPerson;
import com.formygirl.identity.IdentityService;
import jakarta.servlet.http.HttpServletRequest;
import java.time.LocalDate;
import java.util.Map;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.RequestParam;
import org.springframework.web.bind.annotation.RestController;

@RestController
public class StatsController {
    private final IdentityService identityService;
    private final StatsService statsService;

    public StatsController(IdentityService identityService, StatsService statsService) {
        this.identityService = identityService;
        this.statsService = statsService;
    }

    // 这个接口返回当前视角拥有者指定月份的打卡日历。
    @GetMapping("/api/stats/checkin-calendar")
    public ApiResponse<Map<String, Object>> checkinCalendar(
            @RequestParam(required = false) Integer year,
            @RequestParam(required = false) Integer month,
            HttpServletRequest request) {
        CurrentPerson person = identityService.requirePerson(request);
        LocalDate today = LocalDate.now();
        int resolvedYear = year == null ? today.getYear() : year;
        int resolvedMonth = month == null ? today.getMonthValue() : month;
        return ApiResponse.ok(statsService.calendar(person, resolvedYear, resolvedMonth), requestId(request));
    }

    // 这个接口返回当前视角拥有者的坚持情况统计摘要。
    @GetMapping("/api/stats/summary")
    public ApiResponse<Map<String, Object>> summary(HttpServletRequest request) {
        CurrentPerson person = identityService.requirePerson(request);
        return ApiResponse.ok(statsService.summary(person), requestId(request));
    }

    // 这个接口返回绑定管理员视角下对方的统计摘要。
    @GetMapping("/api/bound-user/stats/summary")
    public ApiResponse<Map<String, Object>> boundUserSummary(HttpServletRequest request) {
        CurrentPerson person = identityService.requirePerson(request);
        return ApiResponse.ok(statsService.boundUserSummary(person), requestId(request));
    }

    private String requestId(HttpServletRequest request) {
        return String.valueOf(request.getAttribute(RequestIds.ATTRIBUTE));
    }
}
