package com.formygirl.identity;

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
