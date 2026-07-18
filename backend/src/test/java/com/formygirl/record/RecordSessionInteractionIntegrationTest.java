package com.formygirl.record;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertNotEquals;
import static org.mockito.ArgumentMatchers.any;
import static org.mockito.Mockito.when;
import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.get;
import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.post;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.jsonPath;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.status;

import com.fasterxml.jackson.databind.JsonNode;
import com.fasterxml.jackson.databind.ObjectMapper;
import com.formygirl.common.RequestIds;
import com.formygirl.identity.CurrentPerson;
import com.formygirl.identity.IdentityService;
import com.formygirl.persistence.BusinessRepository;
import jakarta.servlet.http.HttpServletRequest;
import java.io.IOException;
import java.util.ArrayList;
import java.util.List;
import java.util.Map;
import java.util.concurrent.atomic.AtomicInteger;
import okhttp3.mockwebserver.Dispatcher;
import okhttp3.mockwebserver.MockResponse;
import okhttp3.mockwebserver.MockWebServer;
import okhttp3.mockwebserver.RecordedRequest;
import org.junit.jupiter.api.AfterAll;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.Test;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.boot.test.autoconfigure.web.servlet.AutoConfigureMockMvc;
import org.springframework.boot.test.context.SpringBootTest;
import org.springframework.boot.test.mock.mockito.MockBean;
import org.springframework.http.MediaType;
import org.springframework.jdbc.core.JdbcTemplate;
import org.springframework.test.context.DynamicPropertyRegistry;
import org.springframework.test.context.DynamicPropertySource;
import org.springframework.test.web.servlet.MockMvc;
import org.springframework.test.web.servlet.MvcResult;
import org.testcontainers.containers.MySQLContainer;
import org.testcontainers.junit.jupiter.Container;
import org.testcontainers.junit.jupiter.Testcontainers;
import org.testcontainers.utility.DockerImageName;

@Testcontainers
@SpringBootTest(properties = {
        "app.record-workflow-scheduling-enabled=false",
        "app.news-focus-run-on-startup=false"
})
@AutoConfigureMockMvc
class RecordSessionInteractionIntegrationTest {
    private static final CurrentPerson PERSON = new CurrentPerson("person_user", "USER", "用户");
    private static final String THIRD_SESSION_ID = "third_interaction_1";
    private static final MockWebServer THIRD_SERVER = startThirdServer();

    @Container
    private static final MySQLContainer<?> MYSQL = new MySQLContainer<>(DockerImageName.parse("mysql:8.4"))
            .withDatabaseName("for_mygirl_app")
            .withUsername("backend_user")
            .withPassword("backend_password");

    @Autowired
    private MockMvc mockMvc;

    @Autowired
    private ObjectMapper objectMapper;

    @Autowired
    private JdbcTemplate jdbcTemplate;

    @Autowired
    private BusinessRepository repository;

    @Autowired
    private RecordService recordService;

    @MockBean
    private IdentityService identityService;

    private ThirdScenario third;

    @DynamicPropertySource
    static void registerProperties(DynamicPropertyRegistry registry) {
        registry.add("spring.datasource.url", MYSQL::getJdbcUrl);
        registry.add("spring.datasource.username", MYSQL::getUsername);
        registry.add("spring.datasource.password", MYSQL::getPassword);
        registry.add("app.third-base-url", () -> {
            String url = THIRD_SERVER.url("/").toString();
            return url.substring(0, url.length() - 1);
        });
    }

    @BeforeEach
    void setUp() {
        jdbcTemplate.update("DELETE FROM FEISHU_SYNC");
        jdbcTemplate.update("DELETE FROM RECORD_DISPLAY");
        jdbcTemplate.update("DELETE FROM DAILY_RECORD");
        jdbcTemplate.update("DELETE FROM RECORD_WORKFLOW_TASK");
        jdbcTemplate.update("DELETE FROM RECORD_DRAFT");
        jdbcTemplate.update("DELETE FROM RECORD_MESSAGE");
        jdbcTemplate.update("DELETE FROM RECORD_SESSION");
        when(identityService.requirePerson(any(HttpServletRequest.class))).thenReturn(PERSON);
        third = new ThirdScenario(objectMapper);
        THIRD_SERVER.setDispatcher(third);
    }

    @AfterAll
    static void stopThirdServer() throws IOException {
        THIRD_SERVER.shutdown();
    }

    @Test
    void questionFlowUsesRealControllerTransactionAndThirdHttp() throws Exception {
        String question = "两条记录分别要写什么总结？";
        third.waiting("confirmation_question_1", question, "ask_user");
        String sessionId = createSessionAndSendMessage("记录两件事");
        Map<String, Object> waitingTask = processLatestTask(sessionId);

        mockMvc.perform(get("/api/record-sessions/{sessionId}", sessionId))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.data.pendingConfirmation.confirmationId").value("confirmation_question_1"))
                .andExpect(jsonPath("$.data.pendingConfirmation.requestText").value(question))
                .andExpect(jsonPath("$.data.messages[1].sender").value("ai"))
                .andExpect(jsonPath("$.data.messages[1].content").value(question));

        mockMvc.perform(post("/api/record-sessions/{sessionId}/confirm/resume", sessionId)
                        .header(RequestIds.HEADER, "request_answer_1")
                        .contentType(MediaType.APPLICATION_JSON)
                        .content("""
                                {
                                  "thirdSessionId": "third_interaction_1",
                                  "confirmationId": "confirmation_question_1",
                                  "response": "answer",
                                  "content": "第一条是运动，第二条是阅读",
                                  "approved": false
                                }
                                """))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.data.workflowStatus").value("processing"))
                .andExpect(jsonPath("$.data.latestWorkflowTask.triggerType").value("message"))
                .andExpect(jsonPath("$.data.latestWorkflowTask.status").value("submitted"));

        Map<String, Object> closedTask = repository.workflowTask(String.valueOf(waitingTask.get("id")));
        Map<String, Object> latestTask = repository.latestWorkflowTask(sessionId);
        assertEquals("completed", String.valueOf(closedTask.get("status")));
        assertEquals("submitted", String.valueOf(latestTask.get("status")));
        assertEquals("message", String.valueOf(latestTask.get("trigger_type")));
        assertNotEquals(closedTask.get("id"), latestTask.get("id"));
        assertEquals(1, messageCount(sessionId, "ai", question));
        assertEquals(1, messageCount(sessionId, "user", "第一条是运动，第二条是阅读"));
        assertEquals(1, third.resumeBodies.size());
        assertResume(third.resumeBodies.get(0), "confirmation_question_1", "answer", false, "第一条是运动，第二条是阅读");
    }

    @Test
    void approveClosesWaitingTaskAndCreatesLatestResumeTask() throws Exception {
        third.waiting("confirmation_approve_1", "确认写入飞书吗？", "confirm");
        String sessionId = createSessionAndSendMessage("请准备写入");
        Map<String, Object> waitingTask = processLatestTask(sessionId);

        mockMvc.perform(post("/api/record-sessions/{sessionId}/confirm/resume", sessionId)
                        .header(RequestIds.HEADER, "request_approve_1")
                        .contentType(MediaType.APPLICATION_JSON)
                        .content("""
                                {
                                  "clientConfirmId": "client_confirm_1",
                                  "thirdSessionId": "third_interaction_1",
                                  "confirmationId": "confirmation_approve_1",
                                  "response": "approve",
                                  "content": "",
                                  "approved": true
                                }
                                """))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.data.workflowStatus").value("processing"))
                .andExpect(jsonPath("$.data.latestWorkflowTask.triggerType").value("resume"))
                .andExpect(jsonPath("$.data.latestWorkflowTask.clientActionId").value("client_confirm_1"))
                .andExpect(jsonPath("$.data.latestWorkflowTask.status").value("submitted"));

        Map<String, Object> closedTask = repository.workflowTask(String.valueOf(waitingTask.get("id")));
        Map<String, Object> latestTask = repository.latestWorkflowTask(sessionId);
        assertEquals("completed", String.valueOf(closedTask.get("status")));
        assertEquals("submitted", String.valueOf(latestTask.get("status")));
        assertEquals("resume", String.valueOf(latestTask.get("trigger_type")));
        assertNotEquals(closedTask.get("id"), latestTask.get("id"));
        assertResume(third.resumeBodies.get(0), "confirmation_approve_1", "approve", true, "业务前端已确认写入");
    }

    @Test
    void acceptedResumeRollbackCanRepairDriftOnRetry() throws Exception {
        third.waiting("confirmation_old", "请补充今天的总结", "ask_user");
        String sessionId = createSessionAndSendMessage("今天完成了计划");
        Map<String, Object> waitingTask = processLatestTask(sessionId);
        third.advanceConfirmationOnResumeTo = "confirmation_new";
        third.failNextGetAfterResume = true;

        mockMvc.perform(post("/api/record-sessions/{sessionId}/confirm/resume", sessionId)
                        .contentType(MediaType.APPLICATION_JSON)
                        .content(answerBody("confirmation_old", "第一次补充")))
                .andExpect(status().isBadGateway())
                .andExpect(jsonPath("$.code").value("AI_SERVICE_ERROR"));

        Map<String, Object> rolledBackTask = repository.workflowTask(String.valueOf(waitingTask.get("id")));
        assertEquals("waiting_user", String.valueOf(rolledBackTask.get("status")));
        assertEquals("confirmation_old", String.valueOf(rolledBackTask.get("confirmation_id")));
        assertEquals(1, taskCount(sessionId));
        assertEquals(0, messageCount(sessionId, "user", "第一次补充"));

        mockMvc.perform(get("/api/record-sessions/{sessionId}", sessionId))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.data.pendingConfirmation.confirmationId").value("confirmation_new"));

        mockMvc.perform(post("/api/record-sessions/{sessionId}/confirm/resume", sessionId)
                        .contentType(MediaType.APPLICATION_JSON)
                        .content(answerBody("confirmation_new", "第二次补充")))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.data.latestWorkflowTask.status").value("submitted"));

        Map<String, Object> repairedTask = repository.workflowTask(String.valueOf(waitingTask.get("id")));
        Map<String, Object> latestTask = repository.latestWorkflowTask(sessionId);
        assertEquals("completed", String.valueOf(repairedTask.get("status")));
        assertEquals("confirmation_new", String.valueOf(repairedTask.get("confirmation_id")));
        assertEquals("submitted", String.valueOf(latestTask.get("status")));
        assertNotEquals(repairedTask.get("id"), latestTask.get("id"));
        assertEquals(2, taskCount(sessionId));
        assertEquals(1, messageCount(sessionId, "user", "第二次补充"));
        assertEquals(2, third.resumeBodies.size());
    }

    @Test
    void nonWaitingLatestTaskIsRejectedWithoutCallingThird() throws Exception {
        third.waiting("confirmation_1", "请回答", "ask_user");
        String sessionId = createSessionAndSendMessage("等待处理");
        int snapshotCalls = third.snapshotCalls.get();

        mockMvc.perform(post("/api/record-sessions/{sessionId}/confirm/resume", sessionId)
                        .contentType(MediaType.APPLICATION_JSON)
                        .content(answerBody("confirmation_1", "补充")))
                .andExpect(status().isConflict())
                .andExpect(jsonPath("$.code").value("CONFLICT"));

        assertEquals(snapshotCalls, third.snapshotCalls.get());
        assertEquals(0, third.resumeBodies.size());
        assertEquals(1, taskCount(sessionId));
    }

    @Test
    void staleConfirmationIsRejectedBeforeResume() throws Exception {
        third.waiting("confirmation_current", "请回答", "ask_user");
        String sessionId = createSessionAndSendMessage("等待追问");
        Map<String, Object> waitingTask = processLatestTask(sessionId);

        mockMvc.perform(post("/api/record-sessions/{sessionId}/confirm/resume", sessionId)
                        .contentType(MediaType.APPLICATION_JSON)
                        .content(answerBody("confirmation_stale", "补充")))
                .andExpect(status().isConflict())
                .andExpect(jsonPath("$.code").value("CONFLICT"));

        assertEquals(0, third.resumeBodies.size());
        assertEquals("waiting_user", String.valueOf(repository.workflowTask(String.valueOf(waitingTask.get("id"))).get("status")));
        assertEquals(1, taskCount(sessionId));
    }

    @Test
    void thirdConflictRollsBackWithoutCreatingLocalTaskOrMessage() throws Exception {
        third.waiting("confirmation_conflict", "请回答", "ask_user");
        String sessionId = createSessionAndSendMessage("等待追问");
        Map<String, Object> waitingTask = processLatestTask(sessionId);
        third.resumeResponseCode = 409;

        mockMvc.perform(post("/api/record-sessions/{sessionId}/confirm/resume", sessionId)
                        .contentType(MediaType.APPLICATION_JSON)
                        .content(answerBody("confirmation_conflict", "不会保存")))
                .andExpect(status().isConflict())
                .andExpect(jsonPath("$.code").value("STALE_INTERACTION"));

        Map<String, Object> unchangedTask = repository.workflowTask(String.valueOf(waitingTask.get("id")));
        assertEquals("waiting_user", String.valueOf(unchangedTask.get("status")));
        assertEquals(1, taskCount(sessionId));
        assertEquals(0, messageCount(sessionId, "user", "不会保存"));
        assertEquals(1, third.resumeBodies.size());
    }

    private String createSessionAndSendMessage(String content) throws Exception {
        MvcResult createResult = mockMvc.perform(post("/api/record-sessions")
                        .header(RequestIds.HEADER, "request_create")
                        .contentType(MediaType.APPLICATION_JSON)
                        .content("""
                                {
                                  "recordDate": "2026-07-18",
                                  "source": "integration_test"
                                }
                                """))
                .andExpect(status().isOk())
                .andReturn();
        String sessionId = responseData(createResult).path("id").asText();

        mockMvc.perform(post("/api/record-sessions/{sessionId}/messages", sessionId)
                        .header(RequestIds.HEADER, "request_message")
                        .contentType(MediaType.APPLICATION_JSON)
                        .content(objectMapper.writeValueAsString(Map.of(
                                "clientMessageId", "client_message_1",
                                "content", content
                        ))))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.data.workflowStatus").value("processing"))
                .andExpect(jsonPath("$.data.latestWorkflowTask.status").value("submitted"));
        return sessionId;
    }

    private Map<String, Object> processLatestTask(String sessionId) {
        Map<String, Object> task = repository.latestWorkflowTask(sessionId);
        recordService.processWorkflowTask(task);
        Map<String, Object> waitingTask = repository.workflowTask(String.valueOf(task.get("id")));
        assertEquals("waiting_user", String.valueOf(waitingTask.get("status")));
        return waitingTask;
    }

    private JsonNode responseData(MvcResult result) throws IOException {
        return objectMapper.readTree(result.getResponse().getContentAsByteArray()).path("data");
    }

    private String answerBody(String confirmationId, String content) throws IOException {
        return objectMapper.writeValueAsString(Map.of(
                "thirdSessionId", THIRD_SESSION_ID,
                "confirmationId", confirmationId,
                "response", "answer",
                "content", content,
                "approved", false
        ));
    }

    private int taskCount(String sessionId) {
        return jdbcTemplate.queryForObject(
                "SELECT COUNT(*) FROM RECORD_WORKFLOW_TASK WHERE session_id = ?",
                Integer.class,
                sessionId
        );
    }

    private int messageCount(String sessionId, String sender, String content) {
        return jdbcTemplate.queryForObject(
                "SELECT COUNT(*) FROM RECORD_MESSAGE WHERE session_id = ? AND sender = ? AND content = ?",
                Integer.class,
                sessionId,
                sender,
                content
        );
    }

    private void assertResume(String body, String confirmationId, String response, boolean approved, String content) throws IOException {
        JsonNode json = objectMapper.readTree(body);
        assertEquals(confirmationId, json.path("confirmation_id").asText());
        assertEquals(response, json.path("response").asText());
        assertEquals(approved, json.path("approved").asBoolean());
        assertEquals(content, json.path("content").path(0).path("text").asText());
    }

    private static MockWebServer startThirdServer() {
        MockWebServer server = new MockWebServer();
        try {
            server.start();
            return server;
        } catch (IOException exception) {
            throw new ExceptionInInitializerError(exception);
        }
    }

    private static final class ThirdScenario extends Dispatcher {
        private final ObjectMapper json;
        private final List<String> resumeBodies = new ArrayList<>();
        private final AtomicInteger snapshotCalls = new AtomicInteger();
        private String confirmationId = "confirmation_1";
        private String requestText = "请回答";
        private String interactionKind = "ask_user";
        private String advanceConfirmationOnResumeTo;
        private boolean resumeAccepted;
        private boolean failNextGetAfterResume;
        private boolean failedGetConsumed;
        private int resumeResponseCode = 200;

        private ThirdScenario(ObjectMapper json) {
            this.json = json;
        }

        private void waiting(String confirmationId, String requestText, String interactionKind) {
            this.confirmationId = confirmationId;
            this.requestText = requestText;
            this.interactionKind = interactionKind;
        }

        @Override
        public MockResponse dispatch(RecordedRequest request) {
            String path = request.getPath();
            String method = request.getMethod();
            if ("POST".equals(method) && "/workflows/invoke".equals(path)) {
                return jsonResponse(200, Map.of(
                        "session_id", THIRD_SESSION_ID,
                        "status", "queued"
                ));
            }
            if ("GET".equals(method) && ("/workflows/" + THIRD_SESSION_ID).equals(path)) {
                if (resumeAccepted && failNextGetAfterResume && !failedGetConsumed) {
                    failedGetConsumed = true;
                    return jsonResponse(500, Map.of("detail", "temporary failure"));
                }
                if (resumeAccepted) {
                    return jsonResponse(200, Map.of(
                            "session_id", THIRD_SESSION_ID,
                            "status", "running"
                    ));
                }
                return jsonResponse(200, Map.of(
                        "session_id", THIRD_SESSION_ID,
                        "status", "waiting_user",
                        "confirmation", Map.of(
                                "confirmation_id", confirmationId,
                                "request_text", requestText,
                                "interaction_kind", interactionKind
                        )
                ));
            }
            if ("GET".equals(method) && ("/internal/workflows/" + THIRD_SESSION_ID + "/snapshot").equals(path)) {
                snapshotCalls.incrementAndGet();
                return jsonResponse(200, Map.of(
                        "session", Map.of(
                                "sessionId", THIRD_SESSION_ID,
                                "status", "waiting_user"
                        ),
                        "confirmation", Map.of(
                                "confirmationId", confirmationId,
                                "requestText", requestText,
                                "interactionKind", interactionKind,
                                "options", List.of()
                        ),
                        "outputs", Map.of()
                ));
            }
            if ("POST".equals(method) && ("/workflows/" + THIRD_SESSION_ID + "/resume").equals(path)) {
                String body = request.getBody().readUtf8();
                resumeBodies.add(body);
                if (resumeResponseCode != 200) {
                    return jsonResponse(resumeResponseCode, Map.of("detail", "stale interaction"));
                }
                resumeAccepted = true;
                if (advanceConfirmationOnResumeTo != null) {
                    confirmationId = advanceConfirmationOnResumeTo;
                }
                return jsonResponse(200, Map.of(
                        "session_id", THIRD_SESSION_ID,
                        "status", "queued"
                ));
            }
            return jsonResponse(404, Map.of(
                    "detail", "unexpected request",
                    "method", method == null ? "" : method,
                    "path", path == null ? "" : path
            ));
        }

        private MockResponse jsonResponse(int status, Map<String, Object> body) {
            try {
                return new MockResponse()
                        .setResponseCode(status)
                        .setHeader("Content-Type", "application/json")
                        .setBody(json.writeValueAsString(body));
            } catch (IOException exception) {
                return new MockResponse().setResponseCode(500);
            }
        }
    }
}
