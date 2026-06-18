package com.formygirl.auth;

import com.formygirl.common.ApiResponse;
import com.formygirl.common.RequestIds;
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
public class AuthController {
    private final AuthService authService;

    public AuthController(AuthService authService) {
        this.authService = authService;
    }

    // 这个接口使用 MVP 固定账号登录。
    @PostMapping("/login")
    public ApiResponse<Map<String, Object>> login(@Valid @RequestBody LoginRequest request, HttpServletRequest httpRequest) {
        return ApiResponse.ok(authService.login(request.loginName(), request.password()), requestId(httpRequest));
    }

    // 这个接口返回当前登录人。
    @GetMapping("/me")
    public ApiResponse<Map<String, Object>> me(@RequestHeader("Authorization") String authorization, HttpServletRequest httpRequest) {
        CurrentPerson person = authService.requirePerson(authorization);
        return ApiResponse.ok(Map.of("id", person.id(), "role", person.role(), "displayName", person.displayName(), "enabled", true), requestId(httpRequest));
    }

    private String requestId(HttpServletRequest request) {
        return String.valueOf(request.getAttribute(RequestIds.ATTRIBUTE));
    }

    public record LoginRequest(@NotBlank String loginName, @NotBlank String password) {
    }
}
