package com.formygirl.comment;

import com.formygirl.common.Ids;
import java.sql.Timestamp;
import java.time.LocalDateTime;
import java.util.LinkedHashMap;
import java.util.Map;
import org.springframework.dao.EmptyResultDataAccessException;
import org.springframework.jdbc.core.JdbcTemplate;
import org.springframework.stereotype.Repository;

@Repository
public class CommentRepository {
    private final JdbcTemplate jdbcTemplate;

    public CommentRepository(JdbcTemplate jdbcTemplate) {
        this.jdbcTemplate = jdbcTemplate;
    }

    // 这个函数读取正式记录和展示分数。
    public Map<String, Object> record(String recordId) {
        return queryOne(
                """
                SELECT dr.*, rd.score AS display_score
                FROM DAILY_RECORD dr
                LEFT JOIN RECORD_DISPLAY rd ON rd.record_id = dr.id
                WHERE dr.id = ?
                """,
                recordId
        );
    }

    // 这个函数读取记录最新评论。
    public Map<String, Object> latestComment(String recordId) {
        return queryOne(
                """
                SELECT rc.*, p.display_name AS author_display_name
                FROM RECORD_COMMENT rc
                JOIN APP_PERSON p ON p.id = rc.author_user_id
                WHERE rc.record_id = ?
                ORDER BY rc.updated_at DESC, rc.created_at DESC
                LIMIT 1
                """,
                recordId
        );
    }

    // 这个函数新增或更新绑定用户对记录的评论和打分。
    public Map<String, Object> upsertComment(String recordId, String authorUserId, String content, int score) {
        Map<String, Object> existing = queryOne("SELECT * FROM RECORD_COMMENT WHERE record_id = ? AND author_user_id = ?", recordId, authorUserId);
        if (existing.isEmpty()) {
            String id = Ids.newId("comment");
            jdbcTemplate.update(
                    """
                    INSERT INTO RECORD_COMMENT (id, record_id, author_user_id, content, score, visibility, created_at, updated_at)
                    VALUES (?, ?, ?, ?, ?, 'bound_users', ?, ?)
                    """,
                    id,
                    recordId,
                    authorUserId,
                    content,
                    score,
                    Timestamp.valueOf(LocalDateTime.now()),
                    Timestamp.valueOf(LocalDateTime.now())
            );
            return queryOne("SELECT * FROM RECORD_COMMENT WHERE id = ?", id);
        }
        jdbcTemplate.update(
                "UPDATE RECORD_COMMENT SET content = ?, score = ?, updated_at = ? WHERE id = ?",
                content,
                score,
                Timestamp.valueOf(LocalDateTime.now()),
                existing.get("id")
        );
        return queryOne("SELECT * FROM RECORD_COMMENT WHERE id = ?", existing.get("id"));
    }

    private Map<String, Object> queryOne(String sql, Object... args) {
        try {
            return new LinkedHashMap<>(jdbcTemplate.queryForMap(sql, args));
        } catch (EmptyResultDataAccessException exception) {
            return Map.of();
        }
    }
}
