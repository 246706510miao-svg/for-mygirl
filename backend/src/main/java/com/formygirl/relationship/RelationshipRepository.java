package com.formygirl.relationship;

import com.formygirl.common.Ids;
import java.sql.Timestamp;
import java.time.LocalDateTime;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;
import org.springframework.dao.EmptyResultDataAccessException;
import org.springframework.jdbc.core.JdbcTemplate;
import org.springframework.stereotype.Repository;

@Repository
public class RelationshipRepository {
    private final JdbcTemplate jdbcTemplate;

    public RelationshipRepository(JdbcTemplate jdbcTemplate) {
        this.jdbcTemplate = jdbcTemplate;
    }

    // 这个函数读取当前用户的有效绑定关系。
    public Map<String, Object> activeBinding(String requesterUserId) {
        return queryOne(
                """
                SELECT ub.*, p.display_name AS target_display_name, p.role AS target_role, a.login_name AS target_login_name
                FROM USER_BINDING ub
                JOIN APP_PERSON p ON p.id = ub.target_user_id
                LEFT JOIN APP_ACCOUNT a ON a.person_id = p.id
                WHERE ub.requester_user_id = ? AND ub.status = 'active'
                ORDER BY ub.updated_at DESC
                LIMIT 1
                """,
                requesterUserId
        );
    }

    // 这个函数判断 target 是否是 requester 的绑定对象。
    public boolean isBoundTarget(String requesterUserId, String targetUserId) {
        Integer count = jdbcTemplate.queryForObject(
                "SELECT COUNT(*) FROM USER_BINDING WHERE requester_user_id = ? AND target_user_id = ? AND status = 'active'",
                Integer.class,
                requesterUserId,
                targetUserId
        );
        return count != null && count > 0;
    }

    // 这个函数读取绑定权限键。
    public List<String> permissions(String bindingId, String granteeUserId) {
        return jdbcTemplate.queryForList(
                "SELECT permission_key FROM USER_PERMISSION WHERE binding_id = ? AND grantee_user_id = ? AND enabled = TRUE ORDER BY permission_key",
                String.class,
                bindingId,
                granteeUserId
        );
    }

    // 这个函数读取别人发给当前用户的待处理绑定邀请。
    public List<Map<String, Object>> incomingInvitations(String personId) {
        return jdbcTemplate.queryForList(
                """
                SELECT ub.*, p.display_name AS requester_display_name, p.role AS requester_role, a.login_name AS requester_login_name
                FROM USER_BINDING ub
                JOIN APP_PERSON p ON p.id = ub.requester_user_id
                LEFT JOIN APP_ACCOUNT a ON a.person_id = p.id
                WHERE ub.target_user_id = ? AND ub.status = 'pending'
                ORDER BY ub.created_at DESC
                """,
                personId
        );
    }

    // 这个函数读取当前用户发出的待处理绑定邀请。
    public List<Map<String, Object>> outgoingInvitations(String personId) {
        return jdbcTemplate.queryForList(
                """
                SELECT ub.*, p.display_name AS target_display_name, p.role AS target_role, a.login_name AS target_login_name
                FROM USER_BINDING ub
                JOIN APP_PERSON p ON p.id = ub.target_user_id
                LEFT JOIN APP_ACCOUNT a ON a.person_id = p.id
                WHERE ub.requester_user_id = ? AND ub.status = 'pending'
                ORDER BY ub.created_at DESC
                """,
                personId
        );
    }

    // 这个函数按 ID 读取绑定邀请。
    public Map<String, Object> bindingById(String bindingId) {
        return queryOne("SELECT * FROM USER_BINDING WHERE id = ?", bindingId);
    }

    // 这个函数按双方读取绑定记录。
    public Map<String, Object> bindingPair(String requesterUserId, String targetUserId) {
        return queryOne("SELECT * FROM USER_BINDING WHERE requester_user_id = ? AND target_user_id = ?", requesterUserId, targetUserId);
    }

    // 这个函数创建或重新发起 pending 绑定邀请。
    public Map<String, Object> upsertPendingInvitation(String requesterUserId, String targetUserId) {
        Map<String, Object> existing = bindingPair(requesterUserId, targetUserId);
        LocalDateTime now = LocalDateTime.now();
        if (existing.isEmpty()) {
            String id = Ids.newId("binding");
            jdbcTemplate.update(
                    """
                    INSERT INTO USER_BINDING (id, requester_user_id, target_user_id, status, created_at, updated_at)
                    VALUES (?, ?, ?, 'pending', ?, ?)
                    """,
                    id,
                    requesterUserId,
                    targetUserId,
                    Timestamp.valueOf(now),
                    Timestamp.valueOf(now)
            );
            return bindingById(id);
        }
        jdbcTemplate.update(
                "UPDATE USER_BINDING SET status = 'pending', updated_at = ? WHERE id = ?",
                Timestamp.valueOf(now),
                existing.get("id")
        );
        return bindingById(String.valueOf(existing.get("id")));
    }

    // 这个函数更新绑定状态。
    public Map<String, Object> updateBindingStatus(String bindingId, String status) {
        jdbcTemplate.update(
                "UPDATE USER_BINDING SET status = ?, updated_at = ? WHERE id = ?",
                status,
                Timestamp.valueOf(LocalDateTime.now()),
                bindingId
        );
        return bindingById(bindingId);
    }

    // 这个函数确保两个方向都有 active 绑定记录。
    public Map<String, Object> ensureActiveBinding(String requesterUserId, String targetUserId) {
        Map<String, Object> existing = bindingPair(requesterUserId, targetUserId);
        LocalDateTime now = LocalDateTime.now();
        if (existing.isEmpty()) {
            String id = Ids.newId("binding");
            jdbcTemplate.update(
                    """
                    INSERT INTO USER_BINDING (id, requester_user_id, target_user_id, status, created_at, updated_at)
                    VALUES (?, ?, ?, 'active', ?, ?)
                    """,
                    id,
                    requesterUserId,
                    targetUserId,
                    Timestamp.valueOf(now),
                    Timestamp.valueOf(now)
            );
            existing = bindingById(id);
        } else {
            jdbcTemplate.update(
                    "UPDATE USER_BINDING SET status = 'active', updated_at = ? WHERE id = ?",
                    Timestamp.valueOf(now),
                    existing.get("id")
            );
            existing = bindingById(String.valueOf(existing.get("id")));
        }
        ensureDefaultPermissions(String.valueOf(existing.get("id")), requesterUserId);
        return existing;
    }

    // 这个函数为绑定关系补齐默认授权。
    public void ensureDefaultPermissions(String bindingId, String granteeUserId) {
        ensurePermission(bindingId, granteeUserId, "record.comment");
        ensurePermission(bindingId, granteeUserId, "reward.manage");
    }

    // 这个函数读取用户基础信息。
    public Map<String, Object> person(String personId) {
        return queryOne("SELECT * FROM APP_PERSON WHERE id = ?", personId);
    }

    private void ensurePermission(String bindingId, String granteeUserId, String permissionKey) {
        String id = "perm_" + bindingId.substring(Math.max(0, bindingId.length() - 24)) + "_" + permissionKey.replace(".", "_");
        jdbcTemplate.update(
                """
                INSERT INTO USER_PERMISSION (id, binding_id, grantee_user_id, permission_key, enabled, created_at, updated_at)
                VALUES (?, ?, ?, ?, TRUE, ?, ?)
                ON DUPLICATE KEY UPDATE enabled = TRUE, updated_at = VALUES(updated_at)
                """,
                id,
                bindingId,
                granteeUserId,
                permissionKey,
                Timestamp.valueOf(LocalDateTime.now()),
                Timestamp.valueOf(LocalDateTime.now())
        );
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
