package com.formygirl.feishu;

import com.formygirl.common.Ids;
import com.formygirl.common.JsonSupport;
import java.sql.Timestamp;
import java.time.LocalDateTime;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;
import org.springframework.dao.EmptyResultDataAccessException;
import org.springframework.jdbc.core.JdbcTemplate;
import org.springframework.stereotype.Repository;

@Repository
public class FeishuConfigRepository {
    private final JdbcTemplate jdbcTemplate;
    private final JsonSupport json;

    public FeishuConfigRepository(JdbcTemplate jdbcTemplate, JsonSupport json) {
        this.jdbcTemplate = jdbcTemplate;
        this.json = json;
    }

    public Map<String, Object> account(String userId) {
        return queryOne("SELECT * FROM USER_FEISHU_ACCOUNT WHERE user_id = ?", userId);
    }

    public Map<String, Object> upsertAccount(String userId, boolean enabled, String appId, String appSecretCipher, String tenantAccessTokenCipher, String userIdType) {
        Map<String, Object> existing = account(userId);
        LocalDateTime now = LocalDateTime.now();
        if (existing.isEmpty()) {
            String id = Ids.newId("feishu_acc");
            jdbcTemplate.update(
                    """
                    INSERT INTO USER_FEISHU_ACCOUNT (id, user_id, enabled, app_id, app_secret_cipher, tenant_access_token_cipher, user_id_type, created_at, updated_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    id,
                    userId,
                    enabled,
                    blankToNull(appId),
                    blankToNull(appSecretCipher),
                    blankToNull(tenantAccessTokenCipher),
                    defaultUserIdType(userIdType),
                    Timestamp.valueOf(now),
                    Timestamp.valueOf(now)
            );
        } else {
            jdbcTemplate.update(
                    """
                    UPDATE USER_FEISHU_ACCOUNT
                    SET enabled = ?, app_id = ?, app_secret_cipher = ?, tenant_access_token_cipher = ?, user_id_type = ?, updated_at = ?
                    WHERE user_id = ?
                    """,
                    enabled,
                    blankToNull(appId),
                    blankToNull(appSecretCipher),
                    blankToNull(tenantAccessTokenCipher),
                    defaultUserIdType(userIdType),
                    Timestamp.valueOf(now),
                    userId
            );
        }
        return account(userId);
    }

    public List<Map<String, Object>> tables(String userId) {
        return jdbcTemplate.queryForList(
                """
                SELECT * FROM USER_FEISHU_TABLE
                WHERE user_id = ?
                ORDER BY is_default DESC, updated_at DESC
                """,
                userId
        );
    }

    public Map<String, Object> table(String userId, String tableId) {
        return queryOne("SELECT * FROM USER_FEISHU_TABLE WHERE user_id = ? AND id = ?", userId, tableId);
    }

    public Map<String, Object> tableById(String tableId) {
        return queryOne("SELECT * FROM USER_FEISHU_TABLE WHERE id = ?", tableId);
    }

    public Map<String, Object> defaultTable(String userId) {
        Map<String, Object> row = queryOne("SELECT * FROM USER_FEISHU_TABLE WHERE user_id = ? AND enabled = TRUE AND is_default = TRUE ORDER BY updated_at DESC LIMIT 1", userId);
        if (!row.isEmpty()) {
            return row;
        }
        return queryOne("SELECT * FROM USER_FEISHU_TABLE WHERE user_id = ? AND enabled = TRUE ORDER BY updated_at DESC LIMIT 1", userId);
    }

    public Map<String, Object> insertTable(String userId, String accountId, String displayName, String tableUrl, FeishuTableLocation location, Map<String, Object> fieldNameMap, boolean enabled) {
        boolean makeDefault = tables(userId).isEmpty();
        if (makeDefault) {
            clearDefault(userId);
        }
        String id = Ids.newId("feishu_tbl");
        LocalDateTime now = LocalDateTime.now();
        jdbcTemplate.update(
                """
                INSERT INTO USER_FEISHU_TABLE (id, user_id, account_id, display_name, table_url, app_token, table_id, table_name, view_id, is_default, enabled, field_name_map_json, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, CAST(? AS JSON), ?, ?)
                """,
                id,
                userId,
                accountId,
                displayName,
                tableUrl,
                location.appToken(),
                location.tableId(),
                displayName,
                blankToNull(location.viewId()),
                makeDefault,
                enabled,
                json.stringify(fieldNameMap),
                Timestamp.valueOf(now),
                Timestamp.valueOf(now)
        );
        return table(userId, id);
    }

    public Map<String, Object> updateTable(String userId, String tableId, String displayName, String tableUrl, FeishuTableLocation location, Map<String, Object> fieldNameMap, boolean enabled) {
        jdbcTemplate.update(
                """
                UPDATE USER_FEISHU_TABLE
                SET display_name = ?, table_url = ?, app_token = ?, table_id = ?, table_name = ?, view_id = ?, enabled = ?, field_name_map_json = CAST(? AS JSON), updated_at = ?
                WHERE id = ? AND user_id = ?
                """,
                displayName,
                tableUrl,
                location.appToken(),
                location.tableId(),
                displayName,
                blankToNull(location.viewId()),
                enabled,
                json.stringify(fieldNameMap),
                Timestamp.valueOf(LocalDateTime.now()),
                tableId,
                userId
        );
        return table(userId, tableId);
    }

    public Map<String, Object> setDefault(String userId, String tableId) {
        clearDefault(userId);
        jdbcTemplate.update("UPDATE USER_FEISHU_TABLE SET is_default = TRUE, updated_at = ? WHERE user_id = ? AND id = ?", Timestamp.valueOf(LocalDateTime.now()), userId, tableId);
        return table(userId, tableId);
    }

    public void updateTestStatus(String userId, String tableId, String status, String message) {
        jdbcTemplate.update(
                """
                UPDATE USER_FEISHU_TABLE
                SET last_test_status = ?, last_test_message = ?, last_test_at = ?, updated_at = ?
                WHERE user_id = ? AND id = ?
                """,
                status,
                message,
                Timestamp.valueOf(LocalDateTime.now()),
                Timestamp.valueOf(LocalDateTime.now()),
                userId,
                tableId
        );
    }

    private void clearDefault(String userId) {
        jdbcTemplate.update("UPDATE USER_FEISHU_TABLE SET is_default = FALSE WHERE user_id = ?", userId);
    }

    private Map<String, Object> queryOne(String sql, Object... args) {
        try {
            return new LinkedHashMap<>(jdbcTemplate.queryForMap(sql, args));
        } catch (EmptyResultDataAccessException exception) {
            return Map.of();
        }
    }

    private String defaultUserIdType(String value) {
        return value == null || value.isBlank() ? "open_id" : value;
    }

    private String blankToNull(String value) {
        return value == null || value.isBlank() ? null : value;
    }
}
