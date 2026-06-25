package com.formygirl.identity;

import com.formygirl.common.ApiException;
import com.formygirl.common.AppProperties;
import java.security.MessageDigest;
import java.security.SecureRandom;
import java.time.LocalDateTime;
import java.util.HexFormat;
import java.util.Map;
import java.util.Base64;
import org.springframework.http.HttpStatus;
import org.springframework.security.crypto.password.PasswordEncoder;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;

@Service
public class IdentityService {
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
    public Map<String, Object> login(String loginName, String password) {
        Map<String, Object> account = identityRepository.accountByLoginName(normalizeLoginName(loginName));
        if (account.isEmpty() || !enabled(account.get("enabled")) || !enabled(account.get("person_enabled"))) {
            throw unauthorized();
        }
        if (!passwordEncoder.matches(password == null ? "" : password, String.valueOf(account.get("password_hash")))) {
            throw unauthorized();
        }
        identityRepository.updateLastLogin(String.valueOf(account.get("id")));
        return authPayload(newSession(account), personFromAccount(account));
    }

    // 这个函数注册普通用户并立即生成登录会话。
    @Transactional
    public Map<String, Object> register(String loginName, String displayName, String password) {
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
        return authPayload(newSession(account), personFromAccount(account));
    }

    // 这个函数从 Authorization 头解析数据库登录会话。
    public CurrentPerson requirePerson(String authorization) {
        String token = bearerToken(authorization);
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
    public void logout(String authorization) {
        identityRepository.revokeSession(tokenHash(bearerToken(authorization)));
    }

    // 这个函数要求当前登录人为后台运维人员。
    public CurrentPerson requireOpsAdmin(String authorization) {
        CurrentPerson person = requirePerson(authorization);
        if (!person.isOpsAdmin()) {
            throw new ApiException(HttpStatus.FORBIDDEN, "FORBIDDEN", "当前角色无权限");
        }
        return person;
    }

    // 这个函数组装登录响应数据。
    private Map<String, Object> authPayload(String token, CurrentPerson person) {
        return Map.of(
                "accessToken", token,
                "expiresIn", Math.max(1, properties.getSessionTtlHours()) * 3600,
                "person", Map.of(
                        "id", person.id(),
                        "role", person.role(),
                        "displayName", person.displayName(),
                        "enabled", true
                )
        );
    }

    // 这个函数创建一次性明文 token，并只把哈希写入数据库。
    private String newSession(Map<String, Object> account) {
        String token = randomToken();
        LocalDateTime expiresAt = LocalDateTime.now().plusHours(Math.max(1, properties.getSessionTtlHours()));
        identityRepository.insertSession(String.valueOf(account.get("id")), String.valueOf(account.get("person_id")), tokenHash(token), expiresAt);
        return token;
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
}
