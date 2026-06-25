package com.formygirl.identity;

import com.formygirl.common.Ids;
import java.sql.Timestamp;
import java.time.LocalDateTime;
import java.util.LinkedHashMap;
import java.util.Map;
import org.springframework.dao.EmptyResultDataAccessException;
import org.springframework.jdbc.core.JdbcTemplate;
import org.springframework.stereotype.Repository;

@Repository
public class IdentityRepository {
    private final JdbcTemplate jdbcTemplate;

    public IdentityRepository(JdbcTemplate jdbcTemplate) {
        this.jdbcTemplate = jdbcTemplate;
    }

    // 这个函数读取登录人基础信息。
    public Map<String, Object> person(String personId) {
        return queryOne("SELECT * FROM APP_PERSON WHERE id = ?", personId);
    }

    // 这个函数按登录名读取账号和登录人资料。
    public Map<String, Object> accountByLoginName(String loginName) {
        return queryOne(
                """
                SELECT a.*, p.role, p.display_name, p.enabled AS person_enabled, p.current_view_role
                FROM APP_ACCOUNT a
                JOIN APP_PERSON p ON p.id = a.person_id
                WHERE a.login_name = ?
                """,
                loginName
        );
    }

    // 这个函数按 person 读取账号，用于启动时保留历史用户数据。
    public Map<String, Object> accountByPersonId(String personId) {
        return queryOne("SELECT * FROM APP_ACCOUNT WHERE person_id = ?", personId);
    }

    // 这个函数创建普通登录人资料。
    public Map<String, Object> insertPerson(String displayName) {
        String id = Ids.newId("person");
        jdbcTemplate.update(
                """
                INSERT INTO APP_PERSON (id, role, display_name, enabled, created_at, current_view_role)
                VALUES (?, 'USER', ?, TRUE, ?, 'USER')
                """,
                id,
                displayName,
                Timestamp.valueOf(LocalDateTime.now())
        );
        return person(id);
    }

    // 这个函数确保历史 person 存在，并保留原有 person id。
    public Map<String, Object> upsertPerson(String personId, String role, String displayName, String currentViewRole) {
        LocalDateTime now = LocalDateTime.now();
        jdbcTemplate.update(
                """
                INSERT INTO APP_PERSON (id, role, display_name, enabled, created_at, current_view_role)
                VALUES (?, ?, ?, TRUE, ?, ?)
                ON DUPLICATE KEY UPDATE role = VALUES(role), display_name = VALUES(display_name), enabled = TRUE, current_view_role = VALUES(current_view_role)
                """,
                personId,
                role,
                displayName,
                Timestamp.valueOf(now),
                currentViewRole
        );
        return person(personId);
    }

    // 这个函数创建账号，密码只保存哈希。
    public Map<String, Object> insertAccount(String personId, String loginName, String passwordHash) {
        String id = Ids.newId("account");
        LocalDateTime now = LocalDateTime.now();
        jdbcTemplate.update(
                """
                INSERT INTO APP_ACCOUNT (id, person_id, login_name, password_hash, enabled, last_login_at, created_at, updated_at)
                VALUES (?, ?, ?, ?, TRUE, NULL, ?, ?)
                """,
                id,
                personId,
                loginName,
                passwordHash,
                Timestamp.valueOf(now),
                Timestamp.valueOf(now)
        );
        return accountByLoginName(loginName);
    }

    // 这个函数记录账号最近一次登录时间。
    public void updateLastLogin(String accountId) {
        jdbcTemplate.update(
                "UPDATE APP_ACCOUNT SET last_login_at = ?, updated_at = ? WHERE id = ?",
                Timestamp.valueOf(LocalDateTime.now()),
                Timestamp.valueOf(LocalDateTime.now()),
                accountId
        );
    }

    // 这个函数创建登录会话，数据库只保存 token 哈希。
    public void insertSession(String accountId, String personId, String tokenHash, LocalDateTime expiresAt) {
        String id = Ids.newId("session");
        LocalDateTime now = LocalDateTime.now();
        jdbcTemplate.update(
                """
                INSERT INTO APP_LOGIN_SESSION (id, account_id, person_id, token_hash, expires_at, revoked_at, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, NULL, ?, ?)
                """,
                id,
                accountId,
                personId,
                tokenHash,
                Timestamp.valueOf(expiresAt),
                Timestamp.valueOf(now),
                Timestamp.valueOf(now)
        );
    }

    // 这个函数按 token 哈希读取有效登录会话和登录人资料。
    public Map<String, Object> sessionByTokenHash(String tokenHash) {
        return queryOne(
                """
                SELECT s.*, a.login_name, a.enabled AS account_enabled, p.role, p.display_name, p.enabled AS person_enabled
                FROM APP_LOGIN_SESSION s
                JOIN APP_ACCOUNT a ON a.id = s.account_id
                JOIN APP_PERSON p ON p.id = s.person_id
                WHERE s.token_hash = ? AND s.revoked_at IS NULL AND s.expires_at > ?
                """,
                tokenHash,
                Timestamp.valueOf(LocalDateTime.now())
        );
    }

    // 这个函数撤销当前登录会话。
    public void revokeSession(String tokenHash) {
        jdbcTemplate.update(
                "UPDATE APP_LOGIN_SESSION SET revoked_at = ?, updated_at = ? WHERE token_hash = ? AND revoked_at IS NULL",
                Timestamp.valueOf(LocalDateTime.now()),
                Timestamp.valueOf(LocalDateTime.now()),
                tokenHash
        );
    }

    // 这个函数保存普通用户当前手机端视角。
    public void updateCurrentViewRole(String personId, String viewRole) {
        jdbcTemplate.update("UPDATE APP_PERSON SET current_view_role = ? WHERE id = ?", viewRole, personId);
    }

    // 这个函数查询单行数据，查不到时返回空 Map。
    private Map<String, Object> queryOne(String sql, Object... args) {
        try {
            return new LinkedHashMap<>(jdbcTemplate.queryForMap(sql, args));
        } catch (EmptyResultDataAccessException exception) {
            return Map.of();
        }
    }
}
