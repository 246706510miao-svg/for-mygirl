package com.formygirl.newsfocus;

import com.formygirl.common.Ids;
import com.formygirl.common.JsonSupport;
import java.nio.charset.StandardCharsets;
import java.security.MessageDigest;
import java.sql.Date;
import java.sql.Timestamp;
import java.time.LocalDate;
import java.time.LocalDateTime;
import java.time.OffsetDateTime;
import java.time.ZoneOffset;
import java.util.ArrayList;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;
import org.springframework.dao.EmptyResultDataAccessException;
import org.springframework.jdbc.core.JdbcTemplate;
import org.springframework.stereotype.Repository;
import org.springframework.transaction.annotation.Transactional;

@Repository
public class NewsFocusRepository {
    private final JdbcTemplate jdbcTemplate;
    private final JsonSupport json;

    public NewsFocusRepository(JdbcTemplate jdbcTemplate, JsonSupport json) {
        this.jdbcTemplate = jdbcTemplate;
        this.json = json;
    }

    // 这个函数读取此前七日的去重指纹；不含正在覆盖的当天，保证同日重试仍可稳定补齐各分类。
    public List<String> recentFingerprintsBefore(LocalDate date) {
        return jdbcTemplate.queryForList(
                "SELECT fingerprint FROM NEWS_FOCUS_SEEN WHERE seen_at >= ? AND seen_at < ? ORDER BY seen_at DESC",
                String.class,
                Timestamp.valueOf(date.minusDays(7).atStartOfDay()),
                Timestamp.valueOf(date.atStartOfDay())
        );
    }

    // 这个函数读取当天或前一天最近一次可展示的成功结果。
    public Map<String, Object> latestReady(LocalDate date) {
        Map<String, Object> run = queryOne(
                """
                SELECT * FROM NEWS_FOCUS_RUN
                WHERE status = 'ready' AND focus_date BETWEEN ? AND ?
                ORDER BY focus_date DESC, updated_at DESC
                LIMIT 1
                """,
                Date.valueOf(date.minusDays(1)), Date.valueOf(date)
        );
        return withItems(run);
    }

    // 这个函数读取指定日期的完整分组结果，供首页的昨日切换使用。
    public Map<String, Object> readyForDate(LocalDate date) {
        return withItems(queryOne("SELECT * FROM NEWS_FOCUS_RUN WHERE status = 'ready' AND focus_date = ?", Date.valueOf(date)));
    }

    // 这个函数成功时幂等覆盖当天四类条目，并写入去重记忆。
    @Transactional
    public void saveSuccess(LocalDate date, Map<String, Object> generated) {
        Map<String, Object> existing = runForDate(date);
        String runId = existing.isEmpty() ? Ids.newId("newsrun") : String.valueOf(existing.get("id"));
        LocalDateTime now = LocalDateTime.now();
        List<Map<String, Object>> groups = maps(generated.get("groups"));
        int selectedCount = groups.stream().mapToInt(group -> maps(group.get("items")).size()).sum();
        jdbcTemplate.update(
                """
                INSERT INTO NEWS_FOCUS_RUN (id, focus_date, status, source_count, candidate_count, selected_count, generated_at, error_text, created_at, updated_at)
                VALUES (?, ?, 'ready', ?, ?, ?, ?, ?, ?, ?)
                ON DUPLICATE KEY UPDATE status = 'ready', source_count = VALUES(source_count), candidate_count = VALUES(candidate_count), selected_count = VALUES(selected_count), generated_at = VALUES(generated_at), error_text = VALUES(error_text), updated_at = VALUES(updated_at)
                """,
                runId,
                Date.valueOf(date),
                number(generated.get("sourceCount")),
                number(generated.get("candidateCount")),
                selectedCount,
                Timestamp.valueOf(generatedAt(generated.get("generatedAt"), now)),
                sourceErrors(generated),
                Timestamp.valueOf(now),
                Timestamp.valueOf(now)
        );
        String persistedRunId = String.valueOf(runForDate(date).get("id"));
        jdbcTemplate.update("DELETE FROM NEWS_FOCUS_ITEM WHERE run_id = ?", persistedRunId);
        for (Map<String, Object> group : groups) {
            String category = category(group.get("key"));
            List<Map<String, Object>> items = maps(group.get("items"));
            for (int index = 0; index < items.size(); index++) {
                Map<String, Object> item = items.get(index);
                String title = text(item.get("title"), "今日热门");
                jdbcTemplate.update(
                        """
                        INSERT INTO NEWS_FOCUS_ITEM (id, run_id, category_key, rank_no, source_name, source_url, title, summary, tags_json, published_at, created_at)
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                        """,
                        Ids.newId("newsitem"),
                        persistedRunId,
                        category,
                        number(item.get("rank")) > 0 ? number(item.get("rank")) : index + 1,
                        text(item.get("source"), "公开来源"),
                        text(item.get("sourceUrl"), ""),
                        title,
                        text(item.get("summary"), ""),
                        json.stringify(strings(item.get("tags"))),
                        Timestamp.valueOf(generatedAt(item.get("publishedAt"), now)),
                        Timestamp.valueOf(now)
                );
                jdbcTemplate.update(
                        """
                        INSERT INTO NEWS_FOCUS_SEEN (fingerprint, seen_at, created_at)
                        VALUES (?, ?, ?)
                        ON DUPLICATE KEY UPDATE seen_at = VALUES(seen_at)
                        """,
                        text(item.get("dedupeKey"), titleFingerprint(title)),
                        Timestamp.valueOf(now),
                        Timestamp.valueOf(now)
                );
            }
        }
        pruneHistory(date, now);
    }

    // 这个函数保存一次失败记录；若当天已有成功结果，则只记录错误并保留展示内容。
    public void recordFailure(LocalDate date, String errorText) {
        Map<String, Object> existing = runForDate(date);
        LocalDateTime now = LocalDateTime.now();
        if (!existing.isEmpty() && "ready".equals(String.valueOf(existing.get("status")))) {
            jdbcTemplate.update("UPDATE NEWS_FOCUS_RUN SET error_text = ?, updated_at = ? WHERE id = ?", errorText, Timestamp.valueOf(now), existing.get("id"));
            return;
        }
        String runId = existing.isEmpty() ? Ids.newId("newsrun") : String.valueOf(existing.get("id"));
        jdbcTemplate.update(
                """
                INSERT INTO NEWS_FOCUS_RUN (id, focus_date, status, source_count, candidate_count, selected_count, generated_at, error_text, created_at, updated_at)
                VALUES (?, ?, 'failed', 0, 0, 0, NULL, ?, ?, ?)
                ON DUPLICATE KEY UPDATE status = 'failed', error_text = VALUES(error_text), updated_at = VALUES(updated_at)
                """,
                runId, Date.valueOf(date), errorText, Timestamp.valueOf(now), Timestamp.valueOf(now)
        );
    }

    // 这个函数记录空候选；已经成功的当天内容仍保留。
    public void recordEmpty(LocalDate date, Map<String, Object> generated) {
        Map<String, Object> existing = runForDate(date);
        if (!existing.isEmpty() && "ready".equals(String.valueOf(existing.get("status")))) {
            jdbcTemplate.update("UPDATE NEWS_FOCUS_RUN SET error_text = ?, updated_at = ? WHERE id = ?", "本次未收集到可展示候选，保留此前成功结果。", Timestamp.valueOf(LocalDateTime.now()), existing.get("id"));
            return;
        }
        LocalDateTime now = LocalDateTime.now();
        String runId = existing.isEmpty() ? Ids.newId("newsrun") : String.valueOf(existing.get("id"));
        jdbcTemplate.update(
                """
                INSERT INTO NEWS_FOCUS_RUN (id, focus_date, status, source_count, candidate_count, selected_count, generated_at, error_text, created_at, updated_at)
                VALUES (?, ?, 'empty', ?, ?, 0, ?, ?, ?, ?)
                ON DUPLICATE KEY UPDATE status = 'empty', source_count = VALUES(source_count), candidate_count = VALUES(candidate_count), selected_count = 0, generated_at = VALUES(generated_at), error_text = VALUES(error_text), updated_at = VALUES(updated_at)
                """,
                runId, Date.valueOf(date), number(generated.get("sourceCount")), number(generated.get("candidateCount")), Timestamp.valueOf(generatedAt(generated.get("generatedAt"), now)), "本次未收集到可展示候选。", Timestamp.valueOf(now), Timestamp.valueOf(now)
        );
    }

    private Map<String, Object> withItems(Map<String, Object> run) {
        if (run.isEmpty()) {
            return Map.of();
        }
        List<Map<String, Object>> items = jdbcTemplate.queryForList(
                """
                SELECT * FROM NEWS_FOCUS_ITEM WHERE run_id = ?
                ORDER BY FIELD(category_key, 'ai', 'china_focus', 'news', 'open_source'), rank_no ASC
                """,
                String.valueOf(run.get("id"))
        );
        Map<String, Object> result = new LinkedHashMap<>(run);
        result.put("items", items);
        return result;
    }

    private void pruneHistory(LocalDate date, LocalDateTime now) {
        Date displayCutoff = Date.valueOf(date.minusDays(1));
        jdbcTemplate.update(
                "DELETE nfi FROM NEWS_FOCUS_ITEM nfi JOIN NEWS_FOCUS_RUN nfr ON nfr.id = nfi.run_id WHERE nfr.focus_date < ?",
                displayCutoff
        );
        jdbcTemplate.update("DELETE FROM NEWS_FOCUS_RUN WHERE focus_date < ?", displayCutoff);
        jdbcTemplate.update("DELETE FROM NEWS_FOCUS_SEEN WHERE seen_at < ?", Timestamp.valueOf(now.minusDays(7)));
    }

    private Map<String, Object> runForDate(LocalDate date) {
        return queryOne("SELECT * FROM NEWS_FOCUS_RUN WHERE focus_date = ?", Date.valueOf(date));
    }

    private Map<String, Object> queryOne(String sql, Object... args) {
        try {
            return jdbcTemplate.queryForMap(sql, args);
        } catch (EmptyResultDataAccessException exception) {
            return Map.of();
        }
    }

    private List<Map<String, Object>> maps(Object value) {
        if (!(value instanceof List<?> rows)) {
            return List.of();
        }
        List<Map<String, Object>> result = new ArrayList<>();
        for (Object row : rows) {
            if (row instanceof Map<?, ?> map) {
                Map<String, Object> item = new LinkedHashMap<>();
                map.forEach((key, itemValue) -> item.put(String.valueOf(key), itemValue));
                result.add(item);
            }
        }
        return result;
    }

    private List<String> strings(Object value) {
        if (!(value instanceof List<?> rows)) {
            return List.of();
        }
        return rows.stream().map(String::valueOf).filter(item -> !item.isBlank()).toList();
    }

    private int number(Object value) {
        if (value instanceof Number number) {
            return number.intValue();
        }
        try {
            return Integer.parseInt(String.valueOf(value));
        } catch (Exception exception) {
            return 0;
        }
    }

    private String text(Object value, String fallback) {
        if (value == null || String.valueOf(value).isBlank()) {
            return fallback;
        }
        return String.valueOf(value).trim();
    }

    private String category(Object value) {
        String key = text(value, "ai");
        return List.of("ai", "china_focus", "news", "open_source").contains(key) ? key : "ai";
    }

    private LocalDateTime generatedAt(Object value, LocalDateTime fallback) {
        try {
            return OffsetDateTime.parse(String.valueOf(value)).atZoneSameInstant(ZoneOffset.UTC).toLocalDateTime();
        } catch (Exception exception) {
            return fallback;
        }
    }

    private String sourceErrors(Map<String, Object> generated) {
        List<String> errors = strings(generated.get("sourceErrors"));
        if (errors.isEmpty()) {
            return null;
        }
        String value = String.join(" | ", errors);
        return value.substring(0, Math.min(2000, value.length()));
    }

    private String titleFingerprint(String title) {
        try {
            byte[] bytes = MessageDigest.getInstance("SHA-256").digest(title.toLowerCase().replaceAll("[^\\p{L}\\p{N}]+", "").getBytes(StandardCharsets.UTF_8));
            StringBuilder value = new StringBuilder("title:");
            for (byte item : bytes) {
                value.append(String.format("%02x", item));
            }
            return value.toString();
        } catch (Exception exception) {
            return "title:" + Integer.toHexString(title.hashCode());
        }
    }
}
