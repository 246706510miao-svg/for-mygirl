package com.formygirl.user;

import com.formygirl.common.ApiResponse;
import com.formygirl.common.RequestIds;
import com.formygirl.identity.CurrentPerson;
import com.formygirl.identity.IdentityService;
import com.formygirl.record.RecordService;
import com.formygirl.relationship.RelationshipService;
import jakarta.servlet.http.HttpServletRequest;
import java.time.LocalDate;
import java.util.Map;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.RequestHeader;
import org.springframework.web.bind.annotation.RequestParam;
import org.springframework.web.bind.annotation.RestController;

@RestController
public class UserController {
    private final IdentityService identityService;
    private final RecordService recordService;
    private final RelationshipService relationshipService;

    public UserController(IdentityService identityService, RecordService recordService, RelationshipService relationshipService) {
        this.identityService = identityService;
        this.recordService = recordService;
        this.relationshipService = relationshipService;
    }

    // 这个接口返回登录用户首页所需数据。
    @GetMapping("/api/user/home")
    public ApiResponse<Map<String, Object>> home(@RequestHeader("Authorization") String authorization, @RequestParam(required = false) LocalDate date, HttpServletRequest request) {
        CurrentPerson person = identityService.requirePerson(authorization);
        return ApiResponse.ok(recordService.home(person, date == null ? LocalDate.now() : date), requestId(request));
    }

    // 这个接口返回登录用户最近记录列表。
    @GetMapping("/api/user/records")
    public ApiResponse<Map<String, Object>> records(
            @RequestHeader("Authorization") String authorization,
            @RequestParam(required = false) LocalDate fromDate,
            @RequestParam(required = false) LocalDate toDate,
            @RequestParam(defaultValue = "1") int page,
            @RequestParam(defaultValue = "20") int pageSize,
            HttpServletRequest request
    ) {
        CurrentPerson person = identityService.requirePerson(authorization);
        LocalDate end = toDate == null ? LocalDate.now() : toDate;
        LocalDate start = fromDate == null ? end.minusDays(30) : fromDate;
        return ApiResponse.ok(recordService.userRecords(person, start, end, page, pageSize), requestId(request));
    }

    // 这个接口返回当前用户自己的最近记录。
    @GetMapping("/api/records/recent")
    public ApiResponse<Map<String, Object>> recentRecords(
            @RequestHeader("Authorization") String authorization,
            @RequestParam(required = false) LocalDate fromDate,
            @RequestParam(required = false) LocalDate toDate,
            @RequestParam(defaultValue = "1") int page,
            @RequestParam(defaultValue = "20") int pageSize,
            HttpServletRequest request
    ) {
        CurrentPerson person = identityService.requirePerson(authorization);
        LocalDate end = toDate == null ? LocalDate.now() : toDate;
        LocalDate start = fromDate == null ? end.minusDays(30) : fromDate;
        return ApiResponse.ok(recordService.recordsForOwner(person.id(), start, end, page, pageSize), requestId(request));
    }

    // 这个接口返回绑定用户的最近记录。
    @GetMapping("/api/bound-user/records/recent")
    public ApiResponse<Map<String, Object>> boundUserRecentRecords(
            @RequestHeader("Authorization") String authorization,
            @RequestParam(required = false) LocalDate fromDate,
            @RequestParam(required = false) LocalDate toDate,
            @RequestParam(defaultValue = "1") int page,
            @RequestParam(defaultValue = "20") int pageSize,
            HttpServletRequest request
    ) {
        CurrentPerson person = identityService.requirePerson(authorization);
        String ownerUserId = relationshipService.requireBoundAdminTarget(person);
        LocalDate end = toDate == null ? LocalDate.now() : toDate;
        LocalDate start = fromDate == null ? end.minusDays(30) : fromDate;
        return ApiResponse.ok(recordService.recordsForOwner(ownerUserId, start, end, page, pageSize), requestId(request));
    }

    private String requestId(HttpServletRequest request) {
        return String.valueOf(request.getAttribute(RequestIds.ATTRIBUTE));
    }
}
