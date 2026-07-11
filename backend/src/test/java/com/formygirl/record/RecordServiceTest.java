package com.formygirl.record;

import static org.mockito.ArgumentMatchers.any;
import static org.mockito.ArgumentMatchers.anyInt;
import static org.mockito.ArgumentMatchers.anyMap;
import static org.mockito.Mockito.mock;
import static org.mockito.Mockito.verify;
import static org.mockito.Mockito.when;

import com.fasterxml.jackson.databind.ObjectMapper;
import com.formygirl.comment.CommentRepository;
import com.formygirl.comment.CommentService;
import com.formygirl.common.JsonSupport;
import com.formygirl.feishu.FeishuConfigService;
import com.formygirl.persistence.BusinessRepository;
import com.formygirl.thirdclient.ThirdWorkflowClient;
import java.time.LocalDate;
import java.util.Map;
import org.junit.jupiter.api.Test;

class RecordServiceTest {
    private final BusinessRepository repository = mock(BusinessRepository.class);
    private final ThirdWorkflowClient thirdClient = mock(ThirdWorkflowClient.class);
    private final RecordService service = new RecordService(
            repository,
            thirdClient,
            mock(FeishuConfigService.class),
            new JsonSupport(new ObjectMapper()),
            mock(CommentRepository.class),
            mock(CommentService.class)
    );

    @Test
    void terminalResumeMarksTheActiveDraftConfirmed() {
        Map<String, Object> task = Map.of(
                "id", "task_1",
                "session_id", "session_1",
                "trigger_type", "resume",
                "client_action_id", "confirm_1",
                "draft_id", "draft_1",
                "third_session_id", "third_1",
                "request_id", "request_1"
        );
        Map<String, Object> session = Map.of(
                "id", "session_1",
                "user_id", "person_1",
                "record_date", LocalDate.of(2026, 7, 11),
                "status", "previewing"
        );
        Map<String, Object> draft = Map.of(
                "id", "draft_1",
                "session_id", "session_1",
                "draft_json", "{\"title\":\"记录\",\"summary\":\"完成内容\",\"score\":80}",
                "preview_text", "完成内容",
                "status", "active"
        );

        when(repository.requireSession("session_1")).thenReturn(session);
        when(repository.draft("draft_1")).thenReturn(draft);
        when(thirdClient.get("third_1")).thenReturn(Map.of("status", "success"));
        when(repository.insertDailyRecord(session, draft, "confirm_1", null, "request_1", "success"))
                .thenReturn(Map.of("id", "record_1"));
        when(repository.insertFeishuSync(any(), any(), any(), any(), any(), any(), anyInt(), anyMap())).thenReturn(Map.of());
        when(repository.upsertDisplay(any(), any(), any(), anyInt(), any(), anyMap(), anyMap())).thenReturn(Map.of());
        when(repository.insertMessage(any(), any(), any(), any(), any(), any(), any(), any())).thenReturn(Map.of());

        service.processWorkflowTask(task);

        verify(repository).confirmDraft("session_1", "draft_1");
        verify(repository).markSessionConfirmed("session_1");
    }
}
