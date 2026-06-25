package com.formygirl.identity;

import com.formygirl.common.ApiException;
import com.formygirl.common.AppProperties;
import java.util.Map;
import org.springframework.boot.ApplicationArguments;
import org.springframework.boot.ApplicationRunner;
import org.springframework.http.HttpStatus;
import org.springframework.security.crypto.password.PasswordEncoder;
import org.springframework.stereotype.Component;

@Component
public class IdentityBootstrap implements ApplicationRunner {
    private final AppProperties properties;
    private final IdentityRepository repository;
    private final PasswordEncoder passwordEncoder;

    public IdentityBootstrap(AppProperties properties, IdentityRepository repository, PasswordEncoder passwordEncoder) {
        this.properties = properties;
        this.repository = repository;
        this.passwordEncoder = passwordEncoder;
    }

    // 这个函数把历史 person 迁移成真实账号，同时保留原 person id 和业务数据。
    @Override
    public void run(ApplicationArguments args) {
        repository.upsertPerson("person_admin", "OPS_ADMIN", "后台人员", "OPS_ADMIN");
        ensureAccount("person_admin", "admin", properties.getAdminInitialPassword());
        ensureLegacyAccount("person_user", properties.getLegacyUserLoginName(), properties.getLegacyUserInitialPassword());
        ensureLegacyAccount("person_partner", properties.getLegacyPartnerLoginName(), properties.getLegacyPartnerInitialPassword());
    }

    private void ensureLegacyAccount(String personId, String loginName, String initialPassword) {
        if (repository.person(personId).isEmpty()) {
            return;
        }
        ensureAccount(personId, loginName, initialPassword);
    }

    private void ensureAccount(String personId, String loginName, String initialPassword) {
        if (!repository.accountByPersonId(personId).isEmpty()) {
            return;
        }
        String normalizedLoginName = normalizeLoginName(loginName);
        if (!repository.accountByLoginName(normalizedLoginName).isEmpty()) {
            throw new ApiException(HttpStatus.CONFLICT, "BOOTSTRAP_ACCOUNT_CONFLICT", "初始化账号已被其他用户占用：" + normalizedLoginName);
        }
        if (initialPassword == null || initialPassword.length() < 6) {
            throw new ApiException(HttpStatus.INTERNAL_SERVER_ERROR, "BOOTSTRAP_PASSWORD_INVALID", "初始化密码长度需至少 6 位：" + normalizedLoginName);
        }
        repository.insertAccount(personId, normalizedLoginName, passwordEncoder.encode(initialPassword));
    }

    private String normalizeLoginName(String loginName) {
        String value = loginName == null ? "" : loginName.trim().toLowerCase();
        if (!value.matches("[a-z0-9_@.\\-]{3,64}")) {
            throw new ApiException(HttpStatus.INTERNAL_SERVER_ERROR, "BOOTSTRAP_LOGIN_INVALID", "初始化账号格式不合法：" + loginName);
        }
        return value;
    }
}
