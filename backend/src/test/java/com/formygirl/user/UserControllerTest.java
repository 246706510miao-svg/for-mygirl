package com.formygirl.user;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertSame;
import static org.junit.jupiter.api.Assertions.assertThrows;
import static org.mockito.Mockito.mock;
import static org.mockito.Mockito.verify;
import static org.mockito.Mockito.when;

import com.formygirl.common.ApiException;
import com.formygirl.common.ApiResponse;
import com.formygirl.common.RequestIds;
import com.formygirl.identity.CurrentPerson;
import com.formygirl.identity.IdentityService;
import com.formygirl.newsfocus.NewsFocusService;
import com.formygirl.record.RecordService;
import com.formygirl.relationship.RelationshipService;
import java.time.Clock;
import java.time.Instant;
import java.time.LocalDate;
import java.time.ZoneId;
import java.util.List;
import java.util.Map;
import org.junit.jupiter.api.Test;
import org.springframework.mock.web.MockHttpServletRequest;

class UserControllerTest {
    private static final ZoneId SHANGHAI = ZoneId.of("Asia/Shanghai");
    private final IdentityService identityService = mock(IdentityService.class);
    private final RecordService recordService = mock(RecordService.class);
    private final RelationshipService relationshipService = mock(RelationshipService.class);
    private final NewsFocusService newsFocusService = mock(NewsFocusService.class);
    private final Clock clock = Clock.fixed(Instant.parse("2026-07-14T16:30:00Z"), SHANGHAI);
    private final UserController controller = new UserController(identityService, recordService, relationshipService, newsFocusService, clock);

    @Test
    void homeUsesShanghaiDateAndIncludesNewsFocus() {
        MockHttpServletRequest request = request();
        CurrentPerson person = new CurrentPerson("person_1", "USER", "用户");
        LocalDate shanghaiDate = LocalDate.of(2026, 7, 15);
        Map<String, Object> recordHome = Map.of("date", shanghaiDate.toString(), "latestRecord", Map.of());
        Map<String, Object> focus = Map.of(
                "available", true,
                "stale", false,
                "focusDate", shanghaiDate.toString(),
                "groups", List.of(Map.of("key", "ai", "items", List.of(Map.of("title", "中文热门"))))
        );
        when(identityService.requirePerson(request)).thenReturn(person);
        when(recordService.home(person, shanghaiDate)).thenReturn(recordHome);
        when(newsFocusService.homeFocus(shanghaiDate)).thenReturn(focus);

        ApiResponse<Map<String, Object>> response = controller.home(null, request);

        assertEquals("request_1", response.requestId());
        assertEquals(shanghaiDate.toString(), response.data().get("date"));
        assertSame(focus, response.data().get("newsFocus"));
        verify(recordService).home(person, shanghaiDate);
        verify(newsFocusService).homeFocus(shanghaiDate);
    }

    @Test
    void historyRejectsDatesOlderThanYesterdayInShanghai() {
        MockHttpServletRequest request = request();
        when(identityService.requirePerson(request)).thenReturn(new CurrentPerson("person_1", "USER", "用户"));

        ApiException exception = assertThrows(ApiException.class, () -> controller.newsFocus(LocalDate.of(2026, 7, 13), request));

        assertEquals("NEWS_FOCUS_DATE_INVALID", exception.getCode());
    }

    private MockHttpServletRequest request() {
        MockHttpServletRequest request = new MockHttpServletRequest();
        request.setAttribute(RequestIds.ATTRIBUTE, "request_1");
        return request;
    }
}
