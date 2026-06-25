package com.formygirl.identity;

import com.formygirl.common.ApiException;
import com.formygirl.common.AppProperties;
import jakarta.servlet.http.Cookie;
import jakarta.servlet.http.HttpServletRequest;
import java.security.MessageDigest;
import java.security.SecureRandom;
import java.time.LocalDateTime;
import java.util.Base64;
import java.util.HexFormat;
import java.util.Map;
import org.springframework.http.HttpStatus;
import org.springframework.security.crypto.password.PasswordEncoder;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;

@Service
public class IdentityService {
    public static final String DEFAULT_AUTH_COOKIE_NAME = "FOR_MYGIRL_SESSION";

    private final AppProperties properties;
    private final IdentityRepository identityRepository;
    private final PasswordEncoder passwordEncoder;
    private final SecureRandom secureRandom = new SecureRandom();

    public IdentityService(AppProperties properties, IdentityRepository identityRepository, PasswordEncoder passwordEncoder) {
        this.properties = properties;
        this.identityRepository = identityRepository;
        this.passwordEncoder = passwordEncoder;
    }

    // 这个函数使用数据库账号和密码登录。
    @Transactional
    public AuthSession login(String loginName, String password) {
        Map<String, Object> account = identityRepository.accountByLoginName(normalizeLoginName(loginName));
        if (account.isEmpty() || !enabled(account.get("enabled")) || !enabled(account.get("person_enabled"))) {
            throw unauthorized();
        }
        if (!passwordEncoder.matches(password == null ? "" : password, String.valueOf(account.get("password_hash")))) {
            throw unauthorized();
        }
        identityRepository.updateLastLogin(String.valueOf(account.get("id")));
        return newSession(account);
    }

    // 这个函数注册普通用户并立即生成登录会话。
    @Transactional
    public AuthSession register(String loginName, String displayName, String password) {
        String normalizedLoginName = normalizeLoginName(loginName);
        String normalizedDisplayName = requireDisplayName(displayName);
        validatePassword(password);
        if (!identityRepository.accountByLoginName(normalizedLoginName).isEmpty()) {
            throw new ApiException(HttpStatus.CONFLICT, "ACCOUNT_EXISTS", "账号已存在");
        }
        Map<String, Object> person = identityRepository.insertPerson(normalizedDisplayName);
        Map<String, Object> account = identityRepository.insertAccount(
                String.valueOf(person.get("id")),
                normalizedLoginName,
                passwordEncoder.encode(password)
        );
        return newSession(account);
    }

    // 这个函数从浏览器 Cookie 或 Bearer 头解析数据库登录会话。
    public CurrentPerson requirePerson(HttpServletRequest request) {
        return requirePersonByToken(sessionToken(request));
    }

    // 这个函数保留 Bearer token 兼容路径，便于脚本和测试调用。
    public CurrentPerson requirePerson(String authorization) {
        return requirePersonByToken(bearerToken(authorization));
    }

    private CurrentPerson requirePersonByToken(String token) {
        Map<String, Object> session = identityRepository.sessionByTokenHash(tokenHash(token));
        if (session.isEmpty() || !enabled(session.get("account_enabled")) || !enabled(session.get("person_enabled"))) {
            throw new ApiException(HttpStatus.UNAUTHORIZED, "UNAUTHORIZED", "未登录或 token 失效");
        }
        return new CurrentPerson(
                String.valueOf(session.get("person_id")),
                String.valueOf(session.get("role")),
                String.valueOf(session.get("display_name"))
        );
    }

    // 这个函数撤销当前登录会话。
    public void logout(HttpServletRequest request) {
        identityRepository.revokeSession(tokenHash(sessionToken(request)));
    }

    // 这个函数保留 Bearer token 兼容路径，便于脚本和测试调用。
    public void logout(String authorization) {
        identityRepository.revokeSession(tokenHash(bearerToken(authorization)));
    }

    // 这个函数要求当前登录人为后台运维人员。
    public CurrentPerson requireOpsAdmin(HttpServletRequest request) {
        CurrentPerson person = requirePerson(request);
        if (!person.isOpsAdmin()) {
            throw new ApiException(HttpStatus.FORBIDDEN, "FORBIDDEN", "当前角色无权限");
        }
        return person;
    }

    // 这个函数保留 Bearer token 兼容路径，便于脚本和测试调用。
    public CurrentPerson requireOpsAdmin(String authorization) {
        CurrentPerson person = requirePerson(authorization);
        if (!person.isOpsAdmin()) {
            throw new ApiException(HttpStatus.FORBIDDEN, "FORBIDDEN", "当前角色无权限");
        }
        return person;
    }

    // 这个函数组装登录响应数据。
    public Map<String, Object> authPayload(AuthSession session) {
        return Map.of(
                "expiresIn", session.expiresIn(),
                "person", Map.of(
                        "id", session.person().id(),
                        "role", session.person().role(),
                        "displayName", session.person().displayName(),
                        "enabled", true
                )
        );
    }

    // 这个函数创建一次性明文 token，并只把哈希写入数据库；明文只写入 HttpOnly Cookie。
    private AuthSession newSession(Map<String, Object> account) {
        String token = randomToken();
        int expiresIn = sessionTtlSeconds();
        LocalDateTime expiresAt = LocalDateTime.now().plusSeconds(expiresIn);
        identityRepository.insertSession(String.valueOf(account.get("id")), String.valueOf(account.get("person_id")), tokenHash(token), expiresAt);
        return new AuthSession(token, expiresIn, personFromAccount(account));
    }

    private CurrentPerson personFromAccount(Map<String, Object> account) {
        return new CurrentPerson(
                String.valueOf(account.get("person_id")),
                String.valueOf(account.get("role")),
                String.valueOf(account.get("display_name"))
        );
    }

    private String normalizeLoginName(String loginName) {
        String value = loginName == null ? "" : loginName.trim().toLowerCase();
        if (!value.matches("[a-z0-9_@.\\-]{3,64}")) {
            throw new ApiException(HttpStatus.BAD_REQUEST, "INVALID_LOGIN_NAME", "账号需为 3-64 位字母、数字、下划线、点、横线或 @");
        }
        return value;
    }

    private String requireDisplayName(String displayName) {
        String value = displayName == null ? "" : displayName.trim();
        if (value.isBlank() || value.length() > 128) {
            throw new ApiException(HttpStatus.BAD_REQUEST, "INVALID_DISPLAY_NAME", "显示名不能为空且不能超过 128 个字符");
        }
        return value;
    }

    private void validatePassword(String password) {
        if (password == null || password.length() < 6 || password.length() > 128) {
            throw new ApiException(HttpStatus.BAD_REQUEST, "INVALID_PASSWORD", "密码长度需为 6-128 位");
        }
    }

    private boolean enabled(Object value) {
        if (value instanceof Boolean bool) {
            return bool;
        }
        return value != null && ("1".equals(String.valueOf(value)) || Boolean.parseBoolean(String.valueOf(value)));
    }

    private ApiException unauthorized() {
        return new ApiException(HttpStatus.UNAUTHORIZED, "UNAUTHORIZED", "账号或密码错误");
    }

    private String randomToken() {
        byte[] bytes = new byte[32];
        secureRandom.nextBytes(bytes);
        return Base64.getUrlEncoder().withoutPadding().encodeToString(bytes);
    }

    public String tokenHash(String token) {
        try {
            MessageDigest digest = MessageDigest.getInstance("SHA-256");
            return HexFormat.of().formatHex(digest.digest(token.getBytes(java.nio.charset.StandardCharsets.UTF_8)));
        } catch (Exception exception) {
            throw new ApiException(HttpStatus.INTERNAL_SERVER_ERROR, "TOKEN_HASH_ERROR", exception.getMessage());
        }
    }

    // 这个函数从 Bearer 头里提取 token。
    private String bearerToken(String authorization) {
        if (authorization == null || !authorization.startsWith("Bearer ")) {
            throw new ApiException(HttpStatus.UNAUTHORIZED, "UNAUTHORIZED", "未登录或 token 失效");
        }
        return authorization.substring("Bearer ".length()).trim();
    }

    // 这个函数从请求中读取登录 token，浏览器优先使用 HttpOnly Cookie。
    private String sessionToken(HttpServletRequest request) {
        String authorization = request.getHeader("Authorization");
        if (authorization != null && !authorization.isBlank()) {
            return bearerToken(authorization);
        }
        Cookie[] cookies = request.getCookies();
        if (cookies != null) {
            for (Cookie cookie : cookies) {
                if (authCookieName().equals(cookie.getName()) && cookie.getValue() != null && !cookie.getValue().isBlank()) {
                    return cookie.getValue();
                }
            }
        }
        throw new ApiException(HttpStatus.UNAUTHORIZED, "UNAUTHORIZED", "未登录或 token 失效");
    }

    public String authCookieName() {
        String configured = properties.getAuthCookieName();
        return configured == null || configured.isBlank() ? DEFAULT_AUTH_COOKIE_NAME : configured.trim();
    }

    private int sessionTtlSeconds() {
        return Math.max(1, properties.getSessionTtlHours()) * 3600;
    }

    public record AuthSession(String token, int expiresIn, CurrentPerson person) {
    }
}
