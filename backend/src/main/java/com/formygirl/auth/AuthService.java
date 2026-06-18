package com.formygirl.auth;

import com.formygirl.common.ApiException;
import com.formygirl.common.AppProperties;
import java.util.Map;
import org.springframework.http.HttpStatus;
import org.springframework.stereotype.Service;

@Service
public class AuthService {
    private final AppProperties properties;

    public AuthService(AppProperties properties) {
        this.properties = properties;
    }

    // 这个函数用 MVP 固定账号生成开发 token。
    public Map<String, Object> login(String loginName, String password) {
        if ("admin".equals(loginName)) {
            return authPayload(properties.getAdminToken(), new CurrentPerson("person_admin", "ADMIN", "管理员"));
        }
        if ("user".equals(loginName) || "fjl".equals(loginName)) {
            return authPayload(properties.getUserToken(), new CurrentPerson("person_user", "USER", "fjl"));
        }
        throw new ApiException(HttpStatus.UNAUTHORIZED, "UNAUTHORIZED", "账号或密码错误");
    }

    // 这个函数从 Authorization 头解析当前登录人。
    public CurrentPerson requirePerson(String authorization) {
        String token = bearerToken(authorization);
        if (properties.getAdminToken().equals(token)) {
            return new CurrentPerson("person_admin", "ADMIN", "管理员");
        }
        if (properties.getUserToken().equals(token)) {
            return new CurrentPerson("person_user", "USER", "fjl");
        }
        throw new ApiException(HttpStatus.UNAUTHORIZED, "UNAUTHORIZED", "未登录或 token 失效");
    }

    // 这个函数要求当前登录人为管理员。
    public CurrentPerson requireAdmin(String authorization) {
        CurrentPerson person = requirePerson(authorization);
        if (!person.isAdmin()) {
            throw new ApiException(HttpStatus.FORBIDDEN, "FORBIDDEN", "当前角色无权限");
        }
        return person;
    }

    // 这个函数组装登录响应数据。
    private Map<String, Object> authPayload(String token, CurrentPerson person) {
        return Map.of(
                "accessToken", token,
                "expiresIn", 7200,
                "person", Map.of(
                        "id", person.id(),
                        "role", person.role(),
                        "displayName", person.displayName(),
                        "enabled", true
                )
        );
    }

    // 这个函数从 Bearer 头里提取 token。
    private String bearerToken(String authorization) {
        if (authorization == null || !authorization.startsWith("Bearer ")) {
            throw new ApiException(HttpStatus.UNAUTHORIZED, "UNAUTHORIZED", "未登录或 token 失效");
        }
        return authorization.substring("Bearer ".length()).trim();
    }
}
