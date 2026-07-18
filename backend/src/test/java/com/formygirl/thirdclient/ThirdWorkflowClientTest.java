package com.formygirl.thirdclient;

import static com.formygirl.thirdclient.ThirdWorkflowContracts.*;
import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertThrows;
import static org.springframework.test.web.client.match.MockRestRequestMatchers.content;
import static org.springframework.test.web.client.match.MockRestRequestMatchers.method;
import static org.springframework.test.web.client.match.MockRestRequestMatchers.requestTo;
import static org.springframework.test.web.client.response.MockRestResponseCreators.withSuccess;

import com.formygirl.common.ApiException;
import com.formygirl.common.AppProperties;
import com.fasterxml.jackson.databind.ObjectMapper;
import java.nio.file.Files;
import java.nio.file.Path;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.Test;
import org.springframework.http.HttpMethod;
import org.springframework.http.MediaType;
import org.springframework.test.web.client.MockRestServiceServer;
import org.springframework.web.client.RestClient;

class ThirdWorkflowClientTest {
    private static final Path FIXTURE_DIR = Path.of("..", "contracts", "third-workflow", "v1");

    private MockRestServiceServer server;
    private ThirdWorkflowClient client;

    @BeforeEach
    void setUp() {
        RestClient.Builder builder = RestClient.builder();
        server = MockRestServiceServer.bindTo(builder).build();
        AppProperties properties = new AppProperties();
        properties.setThirdBaseUrl("http://third.test");
        client = new ThirdWorkflowClient(builder.build(), properties);
    }

    @Test
    void workflowFixtureDeserializesAndAllowsAdditionalFields() throws Exception {
        String fixture = Files.readString(FIXTURE_DIR.resolve("workflow-queued.json"))
                .replace("\"errorText\": null", "\"errorText\": null, \"futureField\": true");
        server.expect(requestTo("http://third.test/v1/workflows/session_queued"))
                .andExpect(method(HttpMethod.GET))
                .andRespond(withSuccess(fixture, MediaType.APPLICATION_JSON));

        WorkflowResponse response = client.get("session_queued");

        assertEquals("session_queued", response.sessionId());
        assertEquals(WorkflowStatus.QUEUED, response.status());
        server.verify();
    }

    @Test
    void waitingSnapshotFixtureDeserializesToTypedConfirmation() throws Exception {
        server.expect(requestTo("http://third.test/v1/workflows/session_waiting/snapshot"))
                .andRespond(withSuccess(
                        Files.readString(FIXTURE_DIR.resolve("snapshot-confirmation.json")),
                        MediaType.APPLICATION_JSON
                ));

        WorkflowSnapshot snapshot = client.snapshot("session_waiting");

        assertEquals("confirmation_1", snapshot.confirmation().confirmationId());
        assertEquals(InteractionKind.CONFIRM, snapshot.confirmation().interactionKind());
        server.verify();
    }

    @Test
    void renamedConfirmationIdFailsExplicitly() throws Exception {
        String fixture = Files.readString(FIXTURE_DIR.resolve("snapshot-confirmation.json"))
                .replace("\"confirmationId\": \"confirmation_1\"", "\"confirmation_id\": \"confirmation_1\"");
        server.expect(requestTo("http://third.test/v1/workflows/session_waiting/snapshot"))
                .andRespond(withSuccess(fixture, MediaType.APPLICATION_JSON));

        ApiException exception = assertThrows(ApiException.class, () -> client.snapshot("session_waiting"));

        assertEquals("THIRD_CONTRACT_MISMATCH", exception.getCode());
    }

    @Test
    void unknownWorkflowStatusFailsExplicitly() throws Exception {
        String fixture = Files.readString(FIXTURE_DIR.resolve("workflow-running.json"))
                .replace("\"running\"", "\"almost_done\"");
        server.expect(requestTo("http://third.test/v1/workflows/session_running"))
                .andRespond(withSuccess(fixture, MediaType.APPLICATION_JSON));

        ApiException exception = assertThrows(ApiException.class, () -> client.get("session_running"));

        assertEquals("THIRD_CONTRACT_MISMATCH", exception.getCode());
    }

    @Test
    void resumeSerializesOnlyTheCamelCaseV1Request() {
        server.expect(requestTo("http://third.test/v1/workflows/session_waiting/resume"))
                .andExpect(method(HttpMethod.POST))
                .andExpect(content().json(
                        """
                        {
                          "confirmationId": "confirmation_1",
                          "approved": false,
                          "response": "answer",
                          "content": [{"text": "补充内容"}]
                        }
                        """
                ))
                .andRespond(withSuccess(
                        """
                        {
                          "sessionId": "session_waiting",
                          "status": "running",
                          "content": [],
                          "errorText": null
                        }
                        """,
                        MediaType.APPLICATION_JSON
                ));

        WorkflowResponse response = client.resume(
                "session_waiting",
                "confirmation_1",
                "补充内容",
                InteractionResponse.ANSWER.value(),
                false
        );

        assertEquals(WorkflowStatus.RUNNING, response.status());
        server.verify();
    }

    @Test
    void invokeSerializesTypedMetadataAndPrivateMetadata() {
        WorkflowMetadata metadata = new WorkflowMetadata(
                "business_1",
                null,
                null,
                null,
                "message_1",
                new FeishuPublicMetadata("config_1", "测试表", "table_1", "view_1")
        );
        WorkflowPrivateMetadata privateMetadata = new WorkflowPrivateMetadata(
                new FeishuPrivateMetadata(
                        "config_1",
                        new FeishuAccountMetadata(true, "app_id", "secret", "", "open_id"),
                        new FeishuTableMetadata(true, "测试表", "app_token", "table_1", "记录", "view_1", new ObjectMapper().createObjectNode())
                )
        );
        server.expect(requestTo("http://third.test/v1/workflows/invoke"))
                .andExpect(method(HttpMethod.POST))
                .andExpect(content().json(
                        """
                        {
                          "content": [{"text": "新增记录"}],
                          "metadata": {
                            "businessSessionId": "business_1",
                            "businessRecordId": null,
                            "operation": null,
                            "mode": null,
                            "idempotencyKey": "message_1",
                            "feishu": {
                              "configId": "config_1",
                              "displayName": "测试表",
                              "tableId": "table_1",
                              "viewId": "view_1"
                            }
                          },
                          "privateMetadata": {
                            "feishu": {
                              "configId": "config_1",
                              "account": {
                                "enabled": true,
                                "appId": "app_id",
                                "appSecret": "secret",
                                "tenantAccessToken": "",
                                "userIdType": "open_id"
                              },
                              "table": {
                                "enabled": true,
                                "displayName": "测试表",
                                "appToken": "app_token",
                                "tableId": "table_1",
                                "tableName": "记录",
                                "viewId": "view_1",
                                "fieldNameMap": {}
                              }
                            }
                          }
                        }
                        """,
                        false
                ))
                .andRespond(withSuccess(
                        """
                        {"sessionId":"session_1","status":"queued","content":[],"errorText":null}
                        """,
                        MediaType.APPLICATION_JSON
                ));

        assertEquals("session_1", client.invoke("新增记录", metadata, privateMetadata).sessionId());
        server.verify();
    }

    @Test
    void supportEndpointsUseTypedResponses() {
        String session = """
                {
                  "sessionId":"session_1",
                  "status":"running",
                  "originalInput":"测试",
                  "metadata":{}
                }
                """;
        server.expect(requestTo("http://third.test/v1/workflows/session_1/artifacts"))
                .andRespond(withSuccess(
                        """
                        {"sessionId":"session_1","artifacts":[]}
                        """,
                        MediaType.APPLICATION_JSON
                ));
        server.expect(requestTo("http://third.test/v1/workflows/session_1/timeline"))
                .andRespond(withSuccess(
                        "{\"session\":" + session + ",\"decision\":null,\"steps\":[],\"confirmations\":[],\"artifacts\":[]}",
                        MediaType.APPLICATION_JSON
                ));
        server.expect(requestTo("http://third.test/v1/feishu/table-check"))
                .andRespond(withSuccess(
                        """
                        {"status":"ok","message":"已读取字段 0 个。","tableName":"测试表","fieldCount":0,"fieldNames":[]}
                        """,
                        MediaType.APPLICATION_JSON
                ));

        assertEquals("session_1", client.artifacts("session_1").sessionId());
        assertEquals("session_1", client.timeline("session_1").session().sessionId());
        assertEquals("ok", client.checkFeishuTable(WorkflowPrivateMetadata.empty()).status());
        server.verify();
    }

    @Test
    void allWorkflowStateFixturesDeserialize() throws Exception {
        Map<String, String> fixtures = new LinkedHashMap<>();
        for (String name : List.of("queued", "running", "waiting", "success", "failed", "cancelled")) {
            String fixture = Files.readString(FIXTURE_DIR.resolve("workflow-" + name + ".json"));
            String sessionId = "session_" + name;
            fixtures.put(sessionId, fixture);
            server.expect(requestTo("http://third.test/v1/workflows/" + sessionId))
                    .andRespond(withSuccess(fixture, MediaType.APPLICATION_JSON));
        }
        for (String sessionId : fixtures.keySet()) {
            assertEquals(sessionId, client.get(sessionId).sessionId());
        }
        server.verify();
    }
}
