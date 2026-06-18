package com.formygirl.relationship;

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
                SELECT ub.*, p.display_name AS target_display_name, p.role AS target_role
                FROM USER_BINDING ub
                JOIN APP_PERSON p ON p.id = ub.target_user_id
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

    // 这个函数读取用户基础信息。
    public Map<String, Object> person(String personId) {
        return queryOne("SELECT * FROM APP_PERSON WHERE id = ?", personId);
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
