package com.formygirl.user;

import com.formygirl.common.ApiResponse;
import com.formygirl.common.ApiException;
import com.formygirl.common.RequestIds;
import com.formygirl.identity.CurrentPerson;
import com.formygirl.identity.IdentityService;
import com.formygirl.record.RecordService;
import com.formygirl.newsfocus.NewsFocusService;
import com.formygirl.relationship.RelationshipService;
import jakarta.servlet.http.HttpServletRequest;
import java.time.Clock;
import java.time.LocalDate;
import java.time.ZoneId;
import java.util.LinkedHashMap;
import java.util.Map;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.RequestParam;
import org.springframework.web.bind.annotation.RestController;
import org.springframework.http.HttpStatus;

@RestController
public class UserController {
    private static final ZoneId SHANGHAI = ZoneId.of("Asia/Shanghai");
    private final IdentityService identityService;
    private final RecordService recordService;
    private final RelationshipService relationshipService;
    private final NewsFocusService newsFocusService;
    private final Clock clock;

    public UserController(IdentityService identityService, RecordService recordService, RelationshipService relationshipService, NewsFocusService newsFocusService, Clock clock) {
        this.identityService = identityService;
        this.recordService = recordService;
        this.relationshipService = relationshipService;
        this.newsFocusService = newsFocusService;
        this.clock = clock;
    }

    // 这个接口返回登录用户首页所需数据。
    @GetMapping("/api/user/home")
    public ApiResponse<Map<String, Object>> home(@RequestParam(required = false) LocalDate date, HttpServletRequest request) {
        CurrentPerson person = identityService.requirePerson(request);
        LocalDate resolvedDate = date == null ? LocalDate.now(clock.withZone(SHANGHAI)) : date;
        Map<String, Object> result = new LinkedHashMap<>(recordService.home(person, resolvedDate));
        result.put("newsFocus", newsFocusService.homeFocus(resolvedDate));
        return ApiResponse.ok(result, requestId(request));
    }

    // 这个接口只允许读取当天或前一天的共享日榜，供首页抽屉切换往期。
    @GetMapping("/api/user/news-focus")
    public ApiResponse<Map<String, Object>> newsFocus(@RequestParam LocalDate date, HttpServletRequest request) {
        identityService.requirePerson(request);
        LocalDate today = LocalDate.now(clock.withZone(SHANGHAI));
        if (!date.equals(today) && !date.equals(today.minusDays(1))) {
            throw new ApiException(HttpStatus.BAD_REQUEST, "NEWS_FOCUS_DATE_INVALID", "每日热门只保留当天与前一天。");
        }
        return ApiResponse.ok(newsFocusService.historyFocus(date), requestId(request));
    }

    // 这个接口返回登录用户最近记录列表。
    @GetMapping("/api/user/records")
    public ApiResponse<Map<String, Object>> records(
            @RequestParam(required = false) LocalDate fromDate,
            @RequestParam(required = false) LocalDate toDate,
            @RequestParam(defaultValue = "1") int page,
            @RequestParam(defaultValue = "20") int pageSize,
            HttpServletRequest request
    ) {
        CurrentPerson person = identityService.requirePerson(request);
        LocalDate end = toDate == null ? LocalDate.now() : toDate;
        LocalDate start = fromDate == null ? end.minusDays(30) : fromDate;
        return ApiResponse.ok(recordService.userRecords(person, start, end, page, pageSize), requestId(request));
    }

    // 这个接口返回当前用户自己的最近记录。
    @GetMapping("/api/records/recent")
    public ApiResponse<Map<String, Object>> recentRecords(
            @RequestParam(required = false) LocalDate fromDate,
            @RequestParam(required = false) LocalDate toDate,
            @RequestParam(defaultValue = "1") int page,
            @RequestParam(defaultValue = "20") int pageSize,
            HttpServletRequest request
    ) {
        CurrentPerson person = identityService.requirePerson(request);
        LocalDate end = toDate == null ? LocalDate.now() : toDate;
        LocalDate start = fromDate == null ? end.minusDays(30) : fromDate;
        return ApiResponse.ok(recordService.recordsForOwner(person.id(), start, end, page, pageSize), requestId(request));
    }

    // 这个接口返回绑定用户的最近记录。
    @GetMapping("/api/bound-user/records/recent")
    public ApiResponse<Map<String, Object>> boundUserRecentRecords(
            @RequestParam(required = false) LocalDate fromDate,
            @RequestParam(required = false) LocalDate toDate,
            @RequestParam(defaultValue = "1") int page,
            @RequestParam(defaultValue = "20") int pageSize,
            HttpServletRequest request
    ) {
        CurrentPerson person = identityService.requirePerson(request);
        String ownerUserId = relationshipService.requireBoundAdminTarget(person);
        LocalDate end = toDate == null ? LocalDate.now() : toDate;
        LocalDate start = fromDate == null ? end.minusDays(30) : fromDate;
        return ApiResponse.ok(recordService.recordsForOwner(ownerUserId, start, end, page, pageSize), requestId(request));
    }

    private String requestId(HttpServletRequest request) {
        return String.valueOf(request.getAttribute(RequestIds.ATTRIBUTE));
    }
}
