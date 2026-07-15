package com.formygirl.newsfocus;

import static org.mockito.ArgumentMatchers.any;
import static org.mockito.ArgumentMatchers.eq;
import static org.mockito.Mockito.mock;
import static org.mockito.Mockito.never;
import static org.mockito.Mockito.verify;
import static org.mockito.Mockito.when;

import com.fasterxml.jackson.databind.ObjectMapper;
import com.formygirl.common.JsonSupport;
import java.sql.Date;
import java.time.LocalDate;
import java.util.List;
import java.util.Map;
import org.junit.jupiter.api.Test;

class NewsFocusServiceTest {
    private final NewsFocusClient client = mock(NewsFocusClient.class);
    private final NewsFocusRepository repository = mock(NewsFocusRepository.class);
    private final NewsFocusService service = new NewsFocusService(client, repository, new JsonSupport(new ObjectMapper()));

    @Test
    void refreshOverwritesOnlyWhenThirdReturnsGroupedItems() {
        LocalDate date = LocalDate.of(2026, 7, 14);
        when(repository.recentFingerprintsBefore(date)).thenReturn(List.of("title:old"));
        when(client.generate(List.of("title:old"))).thenReturn(Map.of(
                "sourceCount", 2,
                "candidateCount", 3,
                "groups", List.of(Map.of("key", "ai", "items", List.of(Map.of("rank", 1, "title", "中文标题"))))
        ));

        service.refresh(date);

        verify(repository).saveSuccess(eq(date), any());
        verify(repository, never()).recordFailure(any(), any());
        verify(repository, never()).recordEmpty(any(), any());
    }

    @Test
    void refreshFailureDoesNotAttemptToReplaceItems() {
        LocalDate date = LocalDate.of(2026, 7, 14);
        when(repository.recentFingerprintsBefore(date)).thenReturn(List.of());
        when(client.generate(List.of())).thenThrow(new IllegalStateException("third unavailable"));

        service.refresh(date);

        verify(repository).recordFailure(eq(date), org.mockito.ArgumentMatchers.contains("third unavailable"));
        verify(repository, never()).saveSuccess(any(), any());
    }

    @Test
    void homeReturnsEarlierReadyResultAsStale() {
        when(repository.latestReady(LocalDate.of(2026, 7, 14))).thenReturn(Map.of(
                "focus_date", Date.valueOf("2026-07-13"),
                "generated_at", "2026-07-13T07:30:00Z",
                "items", List.of(Map.of(
                        "category_key", "ai",
                        "rank_no", 1,
                        "title", "中文标题",
                        "summary", "中文摘要",
                        "tags_json", "[\"AI\"]",
                        "source_name", "Hacker News",
                        "source_url", "https://example.com/article",
                        "published_at", "2026-07-13T06:00:00Z"
                ))
        ));

        Map<String, Object> result = service.homeFocus(LocalDate.of(2026, 7, 14));

        org.junit.jupiter.api.Assertions.assertEquals(true, result.get("available"));
        org.junit.jupiter.api.Assertions.assertEquals(true, result.get("stale"));
        org.junit.jupiter.api.Assertions.assertEquals("2026-07-13", result.get("focusDate"));
        List<Map<String, Object>> groups = (List<Map<String, Object>>) result.get("groups");
        org.junit.jupiter.api.Assertions.assertEquals("ai", groups.get(0).get("key"));
        org.junit.jupiter.api.Assertions.assertFalse(((List<?>) groups.get(0).get("items")).get(0).toString().contains("score"));
    }

    @Test
    void historyUsesExactRequestedDateWithoutStaleFallback() {
        when(repository.readyForDate(LocalDate.of(2026, 7, 13))).thenReturn(Map.of());

        Map<String, Object> result = service.historyFocus(LocalDate.of(2026, 7, 13));

        org.junit.jupiter.api.Assertions.assertEquals(false, result.get("available"));
        verify(repository).readyForDate(LocalDate.of(2026, 7, 13));
    }
}
