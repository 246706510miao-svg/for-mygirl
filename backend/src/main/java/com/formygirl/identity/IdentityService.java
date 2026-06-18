package com.formygirl.identity;

import com.formygirl.common.ApiException;
import com.formygirl.common.AppProperties;
import java.util.Map;
import org.springframework.http.HttpStatus;
import org.springframework.stereotype.Service;

@Service
public class IdentityService {
    private final AppProperties properties;
    private final IdentityRepository identityRepository;

    public IdentityService(AppProperties properties, IdentityRepository identityRepository) {
        this.properties = properties;
        this.identityRepository = identityRepository;
    }

    // 这个函数用 MVP 固定账号生成开发 token。
    public Map<String, Object> login(String loginName, String password) {
        if ("admin".equals(loginName)) {
            return authPayload(properties.getAdminToken(), person("person_admin", "OPS_ADMIN", "后台人员"));
        }
        if ("partner".equals(loginName) || "ta".equals(loginName)) {
            return authPayload(properties.getPartnerToken(), person("person_partner", "USER", "TA"));
        }
        if ("user".equals(loginName) || "fjl".equals(loginName)) {
            return authPayload(properties.getUserToken(), person("person_user", "USER", "fjl"));
        }
        throw new ApiException(HttpStatus.UNAUTHORIZED, "UNAUTHORIZED", "账号或密码错误");
    }

    // 这个函数从 Authorization 头解析当前登录人。
    public CurrentPerson requirePerson(String authorization) {
        String token = bearerToken(authorization);
        if (properties.getAdminToken().equals(token)) {
            return person("person_admin", "OPS_ADMIN", "后台人员");
        }
        if (properties.getPartnerToken().equals(token)) {
            return person("person_partner", "USER", "TA");
        }
        if (properties.getUserToken().equals(token)) {
            return person("person_user", "USER", "fjl");
        }
        throw new ApiException(HttpStatus.UNAUTHORIZED, "UNAUTHORIZED", "未登录或 token 失效");
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
                "expiresIn", 7200,
                "person", Map.of(
                        "id", person.id(),
                        "role", person.role(),
                        "displayName", person.displayName(),
                        "enabled", true
                )
        );
    }

    // 这个函数优先从业务库读取登录人，避免固定账号和种子数据不一致。
    private CurrentPerson person(String id, String fallbackRole, String fallbackName) {
        Map<String, Object> row = identityRepository.person(id);
        if (row.isEmpty()) {
            return new CurrentPerson(id, fallbackRole, fallbackName);
        }
        return new CurrentPerson(id, String.valueOf(row.get("role")), String.valueOf(row.get("display_name")));
    }

    // 这个函数从 Bearer 头里提取 token。
    private String bearerToken(String authorization) {
        if (authorization == null || !authorization.startsWith("Bearer ")) {
            throw new ApiException(HttpStatus.UNAUTHORIZED, "UNAUTHORIZED", "未登录或 token 失效");
        }
        return authorization.substring("Bearer ".length()).trim();
    }
}
