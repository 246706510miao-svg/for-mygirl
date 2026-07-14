package com.formygirl.newsfocus;

import com.formygirl.common.JsonSupport;
import java.time.LocalDate;
import java.util.ArrayList;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.stereotype.Service;

@Service
public class NewsFocusService {
    private static final Logger log = LoggerFactory.getLogger(NewsFocusService.class);
    private static final List<String> CATEGORIES = List.of("ai", "china_focus", "news", "open_source");
    private static final Map<String, String> CATEGORY_TITLES = Map.of("ai", "AI", "china_focus", "中国大事", "news", "新闻", "open_source", "开源");
    private final NewsFocusClient client;
    private final NewsFocusRepository repository;
    private final JsonSupport json;

    public NewsFocusService(NewsFocusClient client, NewsFocusRepository repository, JsonSupport json) {
        this.client = client;
        this.repository = repository;
        this.json = json;
    }

    // 这个函数生成并发布当天共享热门；只有有效分组才会覆盖当天数据。
    public void refresh(LocalDate date) {
        try {
            Map<String, Object> generated = client.generate(repository.recentFingerprintsBefore(date));
            if (itemCount(generated.get("groups")) == 0) {
                repository.recordEmpty(date, generated);
                log.warn("news focus generated no items for {}", date);
                return;
            }
            repository.saveSuccess(date, generated);
            log.info("news focus published for {}", date);
        } catch (Exception exception) {
            String errorText = "每日热门生成失败：" + message(exception);
            repository.recordFailure(date, errorText);
            log.warn("news focus refresh failed for {}: {}", date, message(exception));
        }
    }

    // 这个函数返回首页共享读取的当天结果；当天失败时最多回退到前一天。
    public Map<String, Object> homeFocus(LocalDate date) {
        return dtoFromRun(repository.latestReady(date), date, true);
    }

    // 这个函数供已登录用户读取当天或昨天的指定日榜，不执行跨日期回退。
    public Map<String, Object> historyFocus(LocalDate date) {
        return dtoFromRun(repository.readyForDate(date), date, false);
    }

    private Map<String, Object> dtoFromRun(Map<String, Object> run, LocalDate requestedDate, boolean allowStale) {
        if (run.isEmpty()) {
            return dto("available", false, "stale", false, "status", "generating", "focusDate", requestedDate.toString(), "groups", emptyGroups());
        }
        LocalDate focusDate = focusDate(run.get("focus_date"), requestedDate);
        boolean stale = allowStale && !focusDate.equals(requestedDate);
        return dto(
                "available", true,
                "stale", stale,
                "status", "ready",
                "focusDate", focusDate.toString(),
                "generatedAt", run.get("generated_at"),
                "groups", groups(run.get("items"))
        );
    }

    private List<Map<String, Object>> groups(Object value) {
        Map<String, List<Map<String, Object>>> byCategory = new LinkedHashMap<>();
        for (String category : CATEGORIES) {
            byCategory.put(category, new ArrayList<>());
        }
        for (Map<String, Object> item : items(value)) {
            String category = String.valueOf(item.getOrDefault("category_key", "ai"));
            List<Map<String, Object>> categoryItems = byCategory.get(category);
            if (categoryItems == null) {
                continue;
            }
            categoryItems.add(dto(
                    "rank", item.get("rank_no"),
                    "title", item.get("title"),
                    "summary", item.get("summary"),
                    "tags", json.list(String.valueOf(item.get("tags_json"))),
                    "source", item.get("source_name"),
                    "sourceUrl", item.get("source_url"),
                    "publishedAt", item.get("published_at")
            ));
        }
        List<Map<String, Object>> result = new ArrayList<>();
        for (String category : CATEGORIES) {
            result.add(dto("key", category, "title", CATEGORY_TITLES.get(category), "items", byCategory.get(category)));
        }
        return result;
    }

    private List<Map<String, Object>> emptyGroups() {
        return CATEGORIES.stream().map(category -> dto("key", category, "title", CATEGORY_TITLES.get(category), "items", List.of())).toList();
    }

    private int itemCount(Object value) {
        return maps(value).stream().mapToInt(group -> items(group.get("items")).size()).sum();
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

    private List<Map<String, Object>> items(Object value) {
        return maps(value);
    }

    private Map<String, Object> dto(Object... entries) {
        Map<String, Object> result = new LinkedHashMap<>();
        for (int index = 0; index + 1 < entries.length; index += 2) {
            result.put(String.valueOf(entries[index]), entries[index + 1]);
        }
        return result;
    }

    private String message(Exception exception) {
        String value = String.valueOf(exception.getMessage());
        return value.length() > 1000 ? value.substring(0, 1000) : value;
    }

    private LocalDate focusDate(Object value, LocalDate fallback) {
        if (value instanceof java.sql.Date sqlDate) {
            return sqlDate.toLocalDate();
        }
        if (value instanceof LocalDate localDate) {
            return localDate;
        }
        try {
            return LocalDate.parse(String.valueOf(value));
        } catch (Exception exception) {
            return fallback;
        }
    }
}
