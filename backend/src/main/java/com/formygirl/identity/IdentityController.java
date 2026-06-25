package com.formygirl.identity;

import com.formygirl.common.ApiResponse;
import com.formygirl.common.AppProperties;
import com.formygirl.common.RequestIds;
import com.formygirl.relationship.RelationshipService;
import jakarta.servlet.http.HttpServletRequest;
import jakarta.validation.Valid;
import jakarta.validation.constraints.NotBlank;
import java.time.Duration;
import java.util.Map;
import org.springframework.http.HttpHeaders;
import org.springframework.http.HttpStatus;
import org.springframework.http.ResponseCookie;
import org.springframework.http.ResponseEntity;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.PostMapping;
import org.springframework.web.bind.annotation.RequestBody;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RestController;

@RestController
@RequestMapping("/api/auth")
public class IdentityController {
    private final IdentityService identityService;
    private final RelationshipService relationshipService;
    private final AppProperties properties;

    public IdentityController(IdentityService identityService, RelationshipService relationshipService, AppProperties properties) {
        this.identityService = identityService;
        this.relationshipService = relationshipService;
        this.properties = properties;
    }

    // 这个接口使用数据库账号密码登录，并把会话 token 写入 HttpOnly Cookie。
    @PostMapping("/login")
    public ResponseEntity<ApiResponse<Map<String, Object>>> login(@Valid @RequestBody LoginRequest request, HttpServletRequest httpRequest) {
        IdentityService.AuthSession session = identityService.login(request.loginName(), request.password());
        return ResponseEntity.ok()
                .header(HttpHeaders.SET_COOKIE, sessionCookie(session.token(), session.expiresIn()).toString())
                .body(ApiResponse.ok(identityService.authPayload(session), requestId(httpRequest)));
    }

    // 这个接口注册普通用户账号并立即登录，同样写入 HttpOnly Cookie。
    @PostMapping("/register")
    public ResponseEntity<ApiResponse<Map<String, Object>>> register(@Valid @RequestBody RegisterRequest request, HttpServletRequest httpRequest) {
        IdentityService.AuthSession session = identityService.register(request.loginName(), request.displayName(), request.password());
        return ResponseEntity.status(HttpStatus.CREATED)
                .header(HttpHeaders.SET_COOKIE, sessionCookie(session.token(), session.expiresIn()).toString())
                .body(ApiResponse.created(identityService.authPayload(session), requestId(httpRequest)));
    }

    // 这个接口退出当前登录会话，并让浏览器删除登录 Cookie。
    @PostMapping("/logout")
    public ResponseEntity<ApiResponse<Map<String, Object>>> logout(HttpServletRequest httpRequest) {
        identityService.logout(httpRequest);
        return ResponseEntity.ok()
                .header(HttpHeaders.SET_COOKIE, expiredSessionCookie().toString())
                .body(ApiResponse.ok(Map.of("status", "logged_out"), requestId(httpRequest)));
    }

    // 这个接口返回当前登录人。
    @GetMapping("/me")
    public ApiResponse<Map<String, Object>> me(HttpServletRequest httpRequest) {
        CurrentPerson person = identityService.requirePerson(httpRequest);
        return ApiResponse.ok(relationshipService.viewContext(person), requestId(httpRequest));
    }

    private String requestId(HttpServletRequest request) {
        return String.valueOf(request.getAttribute(RequestIds.ATTRIBUTE));
    }

    public record LoginRequest(@NotBlank String loginName, @NotBlank String password) {
    }

    public record RegisterRequest(@NotBlank String loginName, @NotBlank String displayName, @NotBlank String password) {
    }

    private ResponseCookie sessionCookie(String token, int expiresIn) {
        return ResponseCookie.from(identityService.authCookieName(), token)
                .httpOnly(true)
                .secure(properties.isAuthCookieSecure())
                .path("/")
                .sameSite("Lax")
                .maxAge(Duration.ofSeconds(expiresIn))
                .build();
    }

    private ResponseCookie expiredSessionCookie() {
        return ResponseCookie.from(identityService.authCookieName(), "")
                .httpOnly(true)
                .secure(properties.isAuthCookieSecure())
                .path("/")
                .sameSite("Lax")
                .maxAge(Duration.ZERO)
                .build();
    }
}
