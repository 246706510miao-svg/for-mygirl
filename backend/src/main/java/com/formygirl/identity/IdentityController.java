package com.formygirl.identity;

import com.formygirl.common.ApiResponse;
import com.formygirl.common.RequestIds;
import com.formygirl.relationship.RelationshipService;
import jakarta.servlet.http.HttpServletRequest;
import jakarta.validation.Valid;
import jakarta.validation.constraints.NotBlank;
import java.util.Map;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.PostMapping;
import org.springframework.web.bind.annotation.RequestBody;
import org.springframework.web.bind.annotation.RequestHeader;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RestController;

@RestController
@RequestMapping("/api/auth")
public class IdentityController {
    private final IdentityService identityService;
    private final RelationshipService relationshipService;

    public IdentityController(IdentityService identityService, RelationshipService relationshipService) {
        this.identityService = identityService;
        this.relationshipService = relationshipService;
    }

    // 这个接口使用数据库账号密码登录。
    @PostMapping("/login")
    public ApiResponse<Map<String, Object>> login(@Valid @RequestBody LoginRequest request, HttpServletRequest httpRequest) {
        return ApiResponse.ok(identityService.login(request.loginName(), request.password()), requestId(httpRequest));
    }

    // 这个接口注册普通用户账号并立即登录。
    @PostMapping("/register")
    public ApiResponse<Map<String, Object>> register(@Valid @RequestBody RegisterRequest request, HttpServletRequest httpRequest) {
        return ApiResponse.created(identityService.register(request.loginName(), request.displayName(), request.password()), requestId(httpRequest));
    }

    // 这个接口退出当前登录会话。
    @PostMapping("/logout")
    public ApiResponse<Map<String, Object>> logout(@RequestHeader("Authorization") String authorization, HttpServletRequest httpRequest) {
        identityService.logout(authorization);
        return ApiResponse.ok(Map.of("status", "logged_out"), requestId(httpRequest));
    }

    // 这个接口返回当前登录人。
    @GetMapping("/me")
    public ApiResponse<Map<String, Object>> me(@RequestHeader("Authorization") String authorization, HttpServletRequest httpRequest) {
        CurrentPerson person = identityService.requirePerson(authorization);
        return ApiResponse.ok(relationshipService.viewContext(person), requestId(httpRequest));
    }

    private String requestId(HttpServletRequest request) {
        return String.valueOf(request.getAttribute(RequestIds.ATTRIBUTE));
    }

    public record LoginRequest(@NotBlank String loginName, @NotBlank String password) {
    }

    public record RegisterRequest(@NotBlank String loginName, @NotBlank String displayName, @NotBlank String password) {
    }
}
