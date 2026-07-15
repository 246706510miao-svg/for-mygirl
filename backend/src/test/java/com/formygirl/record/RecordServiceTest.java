package com.formygirl.record;

import static org.mockito.ArgumentMatchers.any;
import static org.mockito.ArgumentMatchers.anyInt;
import static org.mockito.ArgumentMatchers.anyMap;
import static org.mockito.Mockito.mock;
import static org.mockito.Mockito.verify;
import static org.mockito.Mockito.verifyNoInteractions;
import static org.mockito.Mockito.when;
import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertThrows;

import com.fasterxml.jackson.databind.ObjectMapper;
import com.formygirl.comment.CommentRepository;
import com.formygirl.comment.CommentService;
import com.formygirl.common.JsonSupport;
import com.formygirl.common.ApiException;
import com.formygirl.feishu.FeishuConfigService;
import com.formygirl.identity.CurrentPerson;
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

    @Test
    void staleInteractionIsRejectedBeforeCallingThird() {
        CurrentPerson person = new CurrentPerson("person_1", "USER", "用户");
        when(repository.requireSession("session_1")).thenReturn(Map.of(
                "id", "session_1",
                "user_id", "person_1",
                "status", "active"
        ));
        when(repository.latestWorkflowTask("session_1")).thenReturn(Map.of(
                "id", "task_2",
                "session_id", "session_1",
                "third_session_id", "third_1",
                "confirmation_id", "confirmation_1",
                "status", "submitted"
        ));

        ApiException exception = assertThrows(ApiException.class, () -> service.resumeConfirm(
                person,
                "session_1",
                null,
                null,
                "third_1",
                "confirmation_1",
                "answer",
                "补充内容",
                false,
                "request_1"
        ));

        assertEquals("CONFLICT", exception.getCode());
        verifyNoInteractions(thirdClient);
    }

    @Test
    void currentThirdSnapshotRepairsAConfirmationIdThatDriftedAfterRollback() {
        CurrentPerson person = new CurrentPerson("person_1", "USER", "用户");
        Map<String, Object> sourceTask = Map.of(
                "id", "task_1",
                "session_id", "session_1",
                "third_session_id", "third_1",
                "confirmation_id", "confirmation_old",
                "status", "waiting_user"
        );
        Map<String, Object> repairedTask = Map.of(
                "id", "task_1",
                "session_id", "session_1",
                "third_session_id", "third_1",
                "confirmation_id", "confirmation_new",
                "status", "waiting_user"
        );
        when(repository.requireSession("session_1")).thenReturn(Map.of(
                "id", "session_1",
                "user_id", "person_1",
                "status", "active"
        ));
        when(repository.latestWorkflowTask("session_1")).thenReturn(sourceTask);
        when(thirdClient.snapshot("third_1")).thenReturn(Map.of(
                "confirmation", Map.of("confirmationId", "confirmation_new")
        ));
        when(repository.markWorkflowTaskWaitingUser("task_1", "confirmation_new", null)).thenReturn(repairedTask);

        ApiException exception = assertThrows(ApiException.class, () -> service.resumeConfirm(
                person,
                "session_1",
                null,
                null,
                "third_1",
                "confirmation_new",
                "unsupported",
                "补充内容",
                false,
                "request_1"
        ));

        assertEquals("BAD_REQUEST", exception.getCode());
        verify(repository).markWorkflowTaskWaitingUser("task_1", "confirmation_new", null);
    }

    @Test
    void waitingInteractionStoresTheRealQuestionAsAnAiMessage() {
        Map<String, Object> task = Map.of(
                "id", "task_1",
                "session_id", "session_1",
                "trigger_type", "message",
                "source_message_id", "message_1",
                "third_session_id", "third_1",
                "request_id", "request_1"
        );
        Map<String, Object> session = Map.of(
                "id", "session_1",
                "user_id", "person_1",
                "record_date", LocalDate.of(2026, 7, 15),
                "status", "active"
        );
        String question = "两条记录分别要写什么总结？";

        when(repository.requireSession("session_1")).thenReturn(session);
        when(repository.message("message_1")).thenReturn(Map.of("content", "记录两件事"));
        when(thirdClient.get("third_1")).thenReturn(Map.of(
                "status", "waiting_user",
                "confirmation", Map.of("confirmation_id", "confirmation_1", "request_text", question)
        ));
        when(thirdClient.snapshot("third_1")).thenReturn(Map.of(
                "confirmation", Map.of("confirmationId", "confirmation_1", "requestText", question),
                "outputs", Map.of()
        ));

        service.processWorkflowTask(task);

        verify(repository).insertMessage("session_1", "ai", "text", question, null, null, "third_1", "request_1");
        verify(repository).markWorkflowTaskWaitingUser("task_1", "confirmation_1", null);
    }
}
