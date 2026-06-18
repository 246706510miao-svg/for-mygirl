package com.formygirl.comment;

import com.formygirl.common.ApiException;
import com.formygirl.identity.CurrentPerson;
import com.formygirl.points.PointService;
import com.formygirl.relationship.RelationshipService;
import java.sql.Date;
import java.time.LocalDate;
import java.util.LinkedHashMap;
import java.util.Map;
import org.springframework.http.HttpStatus;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;

@Service
public class CommentService {
    private final CommentRepository commentRepository;
    private final RelationshipService relationshipService;
    private final PointService pointService;

    public CommentService(CommentRepository commentRepository, RelationshipService relationshipService, PointService pointService) {
        this.commentRepository = commentRepository;
        this.relationshipService = relationshipService;
        this.pointService = pointService;
    }

    // 这个函数保存绑定管理员对记录的评论和打分，并刷新记录积分。
    @Transactional
    public Map<String, Object> save(CurrentPerson author, String recordId, String content, int score) {
        String targetUserId = relationshipService.requireBoundAdminTarget(author);
        if (content == null || content.isBlank() || score < 0 || score > 100) {
            throw new ApiException(HttpStatus.BAD_REQUEST, "BAD_REQUEST", "评论不能为空，分数需为 0-100");
        }
        Map<String, Object> record = commentRepository.record(recordId);
        if (record.isEmpty()) {
            throw new ApiException(HttpStatus.NOT_FOUND, "NOT_FOUND", "记录不存在");
        }
        if (!targetUserId.equals(String.valueOf(record.get("user_id")))) {
            throw new ApiException(HttpStatus.FORBIDDEN, "FORBIDDEN", "只能评论绑定用户的记录");
        }
        Map<String, Object> comment = commentRepository.upsertComment(recordId, author.id(), content.trim(), score);
        Map<String, Object> points = pointService.applyRecordScore(
                targetUserId,
                recordId,
                recordDate(record.get("record_date")),
                intValue(record.get("ai_score"), intValue(record.get("display_score"), 0)),
                score
        );
        return dto("comment", commentDto(comment), "points", points);
    }

    // 这个函数把评论行转换为前端 DTO。
    public Map<String, Object> commentDto(Map<String, Object> row) {
        if (row == null || row.isEmpty()) {
            return Map.of();
        }
        return dto(
                "id", row.get("id"),
                "recordId", row.get("record_id"),
                "authorUserId", row.get("author_user_id"),
                "authorDisplayName", row.get("author_display_name"),
                "content", row.get("content"),
                "score", row.get("score"),
                "updatedAt", row.get("updated_at")
        );
    }

    private LocalDate recordDate(Object value) {
        if (value instanceof Date date) {
            return date.toLocalDate();
        }
        if (value instanceof java.time.LocalDate localDate) {
            return localDate;
        }
        return LocalDate.parse(String.valueOf(value));
    }

    private Map<String, Object> dto(Object... entries) {
        Map<String, Object> result = new LinkedHashMap<>();
        for (int index = 0; index + 1 < entries.length; index += 2) {
            result.put(String.valueOf(entries[index]), entries[index + 1]);
        }
        return result;
    }

    private int intValue(Object value, int fallback) {
        if (value instanceof Number number) {
            return number.intValue();
        }
        try {
            return Integer.parseInt(String.valueOf(value));
        } catch (Exception exception) {
            return fallback;
        }
    }
}
