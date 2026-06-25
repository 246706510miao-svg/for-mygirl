package com.formygirl.points;

import com.formygirl.common.ApiResponse;
import com.formygirl.common.RequestIds;
import com.formygirl.identity.CurrentPerson;
import com.formygirl.identity.IdentityService;
import jakarta.servlet.http.HttpServletRequest;
import jakarta.validation.Valid;
import jakarta.validation.constraints.Min;
import jakarta.validation.constraints.NotBlank;
import java.time.LocalDate;
import java.util.Map;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.PathVariable;
import org.springframework.web.bind.annotation.PostMapping;
import org.springframework.web.bind.annotation.RequestBody;
import org.springframework.web.bind.annotation.RestController;

@RestController
public class PointController {
    private final IdentityService identityService;
    private final PointService pointService;

    public PointController(IdentityService identityService, PointService pointService) {
        this.identityService = identityService;
        this.pointService = pointService;
    }

    // 这个接口执行当前用户每日签到。
    @PostMapping("/api/points/checkins")
    public ApiResponse<Map<String, Object>> checkin(HttpServletRequest request) {
        CurrentPerson person = identityService.requirePerson(request);
        return ApiResponse.ok(pointService.checkin(person, LocalDate.now()), requestId(request));
    }

    // 这个接口返回当前用户和当前视角拥有者的积分摘要。
    @GetMapping("/api/points/summary")
    public ApiResponse<Map<String, Object>> summary(HttpServletRequest request) {
        CurrentPerson person = identityService.requirePerson(request);
        return ApiResponse.ok(pointService.summary(person), requestId(request));
    }

    // 这个接口返回当前视角可见奖品。
    @GetMapping("/api/rewards")
    public ApiResponse<Map<String, Object>> rewards(HttpServletRequest request) {
        CurrentPerson person = identityService.requirePerson(request);
        return ApiResponse.ok(pointService.rewards(person), requestId(request));
    }

    // 这个接口给绑定用户添加奖品。
    @PostMapping("/api/rewards")
    public ApiResponse<Map<String, Object>> addReward(@Valid @RequestBody RewardRequest body, HttpServletRequest request) {
        CurrentPerson person = identityService.requirePerson(request);
        return ApiResponse.created(pointService.addReward(person, body.title(), body.description(), body.costPoints()), requestId(request));
    }

    // 这个接口兑换当前用户自己的奖品。
    @PostMapping("/api/rewards/{rewardId}/redeem")
    public ApiResponse<Map<String, Object>> redeem(@PathVariable String rewardId, HttpServletRequest request) {
        CurrentPerson person = identityService.requirePerson(request);
        return ApiResponse.ok(pointService.redeem(person, rewardId), requestId(request));
    }

    // 这个接口返回当前视角下的兑换记录。
    @GetMapping("/api/reward-redemptions")
    public ApiResponse<Map<String, Object>> redemptions(HttpServletRequest request) {
        CurrentPerson person = identityService.requirePerson(request);
        return ApiResponse.ok(pointService.redemptions(person), requestId(request));
    }

    private String requestId(HttpServletRequest request) {
        return String.valueOf(request.getAttribute(RequestIds.ATTRIBUTE));
    }

    public record RewardRequest(@NotBlank String title, String description, @Min(1) int costPoints) {
    }
}
