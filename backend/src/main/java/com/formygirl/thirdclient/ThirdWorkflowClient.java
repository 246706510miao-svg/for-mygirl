package com.formygirl.thirdclient;

import static com.formygirl.thirdclient.ThirdWorkflowContracts.*;

import com.formygirl.common.ApiException;
import com.formygirl.common.AppProperties;
import java.util.List;
import org.springframework.http.HttpStatus;
import org.springframework.stereotype.Component;
import org.springframework.web.client.ResourceAccessException;
import org.springframework.web.client.RestClient;
import org.springframework.web.client.RestClientException;
import org.springframework.web.client.RestClientResponseException;

@Component
public class ThirdWorkflowClient {
    private final RestClient restClient;
    private final AppProperties properties;

    public ThirdWorkflowClient(RestClient restClient, AppProperties properties) {
        this.restClient = restClient;
        this.properties = properties;
    }

    // 这个函数只提交确认结果，不等待 workflow 终态。
    public WorkflowResponse resume(String thirdSessionId, String confirmationId, String text, boolean approved) {
        return resume(thirdSessionId, confirmationId, text, approved ? "approve" : "cancel", approved);
    }

    // 这个函数提交明确的交互类型，支持追问回答和确认修改。
    public WorkflowResponse resume(String thirdSessionId, String confirmationId, String text, String response, boolean approved) {
        try {
            ResumeWorkflowRequest body = new ResumeWorkflowRequest(
                    confirmationId,
                    approved,
                    InteractionResponse.fromValue(response),
                    List.of(new ContentPart(text))
            );
            WorkflowResponse result = restClient.post()
                    .uri(properties.getThirdBaseUrl() + "/v1/workflows/{sessionId}/resume", thirdSessionId)
                    .body(body)
                    .retrieve()
                    .body(WorkflowResponse.class);
            return requireWorkflowResponse(result, "resume");
        } catch (RestClientResponseException exception) {
            if (exception.getStatusCode().value() == 400 || exception.getStatusCode().value() == 409) {
                throw new ApiException(HttpStatus.CONFLICT, "STALE_INTERACTION", "刚才的问题已经更新，请刷新后继续");
            }
            throw new ApiException(HttpStatus.BAD_GATEWAY, "AI_SERVICE_ERROR", "third workflow 暂时无法继续，请稍后重试");
        } catch (ResourceAccessException exception) {
            throw new ApiException(HttpStatus.BAD_GATEWAY, "AI_SERVICE_ERROR", "third workflow 暂时无法继续，请稍后重试");
        } catch (ApiException exception) {
            throw exception;
        } catch (RestClientException | IllegalArgumentException exception) {
            throw contractMismatch("resume", exception);
        }
    }

    // 这个函数查询 workflow artifact 明细。
    public WorkflowArtifacts artifacts(String thirdSessionId) {
        try {
            WorkflowArtifacts result = restClient.get()
                    .uri(properties.getThirdBaseUrl() + "/v1/workflows/{sessionId}/artifacts", thirdSessionId)
                    .retrieve()
                    .body(WorkflowArtifacts.class);
            if (result == null || isBlank(result.sessionId()) || result.artifacts() == null) {
                throw contractMismatch("artifacts", null);
            }
            return result;
        } catch (RestClientResponseException exception) {
            throw serviceUnavailable("artifact 查询");
        } catch (ResourceAccessException exception) {
            throw serviceUnavailable("artifact 查询");
        } catch (ApiException exception) {
            throw exception;
        } catch (RestClientException | IllegalArgumentException exception) {
            throw contractMismatch("artifacts", exception);
        }
    }

    // 这个函数查询 workflow 统一快照，供后端按契约消费全量 JSON。
    public WorkflowSnapshot snapshot(String thirdSessionId) {
        try {
            WorkflowSnapshot result = restClient.get()
                    .uri(properties.getThirdBaseUrl() + "/v1/workflows/{sessionId}/snapshot", thirdSessionId)
                    .retrieve()
                    .body(WorkflowSnapshot.class);
            return requireSnapshot(result);
        } catch (RestClientResponseException exception) {
            throw serviceUnavailable("snapshot 查询");
        } catch (ResourceAccessException exception) {
            throw serviceUnavailable("snapshot 查询");
        } catch (ApiException exception) {
            throw exception;
        } catch (RestClientException | IllegalArgumentException exception) {
            throw contractMismatch("snapshot", exception);
        }
    }

    // 这个函数查询 workflow 时间线摘要。
    public WorkflowTimeline timeline(String thirdSessionId) {
        try {
            WorkflowTimeline result = restClient.get()
                    .uri(properties.getThirdBaseUrl() + "/v1/workflows/{sessionId}/timeline", thirdSessionId)
                    .retrieve()
                    .body(WorkflowTimeline.class);
            if (result == null || result.session() == null || isBlank(result.session().sessionId())
                    || result.steps() == null || result.confirmations() == null || result.artifacts() == null) {
                throw contractMismatch("timeline", null);
            }
            return result;
        } catch (RestClientResponseException exception) {
            throw serviceUnavailable("timeline 查询");
        } catch (ResourceAccessException exception) {
            throw serviceUnavailable("timeline 查询");
        } catch (ApiException exception) {
            throw exception;
        } catch (RestClientException | IllegalArgumentException exception) {
            throw contractMismatch("timeline", exception);
        }
    }

    // 这个函数让 third 使用私有飞书配置测试表连接。
    public FeishuTableCheckResponse checkFeishuTable(WorkflowPrivateMetadata privateMetadata) {
        try {
            FeishuTableCheckResponse result = restClient.post()
                    .uri(properties.getThirdBaseUrl() + "/v1/feishu/table-check")
                    .body(new FeishuTableCheckRequest(privateMetadata == null ? WorkflowPrivateMetadata.empty() : privateMetadata))
                    .retrieve()
                    .body(FeishuTableCheckResponse.class);
            if (result == null || isBlank(result.status()) || result.message() == null || result.fieldNames() == null) {
                throw contractMismatch("feishu table-check", null);
            }
            return result;
        } catch (RestClientResponseException exception) {
            throw serviceUnavailable("飞书表测试");
        } catch (ResourceAccessException exception) {
            throw serviceUnavailable("飞书表测试");
        } catch (ApiException exception) {
            throw exception;
        } catch (RestClientException | IllegalArgumentException exception) {
            throw contractMismatch("feishu table-check", exception);
        }
    }

    // 这个函数让 third 统一解析 Base/Wiki 多维表格 URL，并返回可持久化的真实表定位信息。
    public FeishuTableResolveResponse resolveFeishuTable(String tableUrl, WorkflowPrivateMetadata privateMetadata) {
        try {
            FeishuTableResolveResponse result = restClient.post()
                    .uri(properties.getThirdBaseUrl() + "/v1/feishu/table-resolve")
                    .body(new FeishuTableResolveRequest(
                            tableUrl,
                            privateMetadata == null ? WorkflowPrivateMetadata.empty() : privateMetadata
                    ))
                    .retrieve()
                    .body(FeishuTableResolveResponse.class);
            if (result == null || isBlank(result.status()) || result.message() == null) {
                throw contractMismatch("feishu table-resolve", null);
            }
            if (!"ok".equals(result.status())) {
                String errorCode = isBlank(result.errorCode()) ? "FEISHU_WIKI_RESOLVE_FAILED" : result.errorCode();
                throw new ApiException(HttpStatus.BAD_REQUEST, errorCode, result.message());
            }
            if (isBlank(result.sourceType()) || isBlank(result.appToken()) || isBlank(result.tableId()) || result.viewId() == null) {
                throw contractMismatch("feishu table-resolve", null);
            }
            return result;
        } catch (RestClientResponseException exception) {
            throw serviceUnavailable("飞书表 URL 解析");
        } catch (ResourceAccessException exception) {
            throw serviceUnavailable("飞书表 URL 解析");
        } catch (ApiException exception) {
            throw exception;
        } catch (RestClientException | IllegalArgumentException exception) {
            throw contractMismatch("feishu table-resolve", exception);
        }
    }

    // 这个函数提交 workflow。
    public WorkflowResponse invoke(String text, WorkflowMetadata metadata, WorkflowPrivateMetadata privateMetadata) {
        try {
            InvokeWorkflowRequest body = new InvokeWorkflowRequest(
                    List.of(new ContentPart(text)),
                    metadata,
                    privateMetadata == null ? WorkflowPrivateMetadata.empty() : privateMetadata
            );
            WorkflowResponse result = restClient.post()
                    .uri(properties.getThirdBaseUrl() + "/v1/workflows/invoke")
                    .body(body)
                    .retrieve()
                    .body(WorkflowResponse.class);
            return requireWorkflowResponse(result, "invoke");
        } catch (RestClientResponseException exception) {
            throw serviceUnavailable("调用");
        } catch (ResourceAccessException exception) {
            throw serviceUnavailable("调用");
        } catch (ApiException exception) {
            throw exception;
        } catch (RestClientException | IllegalArgumentException exception) {
            throw contractMismatch("invoke", exception);
        }
    }

    // 这个函数查询 workflow 当前状态。
    public WorkflowResponse get(String thirdSessionId) {
        try {
            WorkflowResponse result = restClient.get()
                    .uri(properties.getThirdBaseUrl() + "/v1/workflows/{sessionId}", thirdSessionId)
                    .retrieve()
                    .body(WorkflowResponse.class);
            return requireWorkflowResponse(result, "get");
        } catch (RestClientResponseException exception) {
            throw serviceUnavailable("查询");
        } catch (ResourceAccessException exception) {
            throw serviceUnavailable("查询");
        } catch (ApiException exception) {
            throw exception;
        } catch (RestClientException | IllegalArgumentException exception) {
            throw contractMismatch("get", exception);
        }
    }

    private WorkflowResponse requireWorkflowResponse(WorkflowResponse response, String endpoint) {
        if (response == null || isBlank(response.sessionId()) || response.status() == null || response.content() == null) {
            throw contractMismatch(endpoint, null);
        }
        return response;
    }

    private WorkflowSnapshot requireSnapshot(WorkflowSnapshot snapshot) {
        if (snapshot == null || snapshot.session() == null || snapshot.session().status() == null
                || isBlank(snapshot.session().sessionId()) || snapshot.outputs() == null
                || snapshot.artifactsByKey() == null || snapshot.artifacts() == null) {
            throw contractMismatch("snapshot", null);
        }
        if (snapshot.session().status() == WorkflowStatus.WAITING_USER) {
            WorkflowConfirmation confirmation = snapshot.confirmation();
            if (confirmation == null || isBlank(confirmation.confirmationId())
                    || isBlank(confirmation.requestText()) || confirmation.interactionKind() == null
                    || confirmation.options() == null) {
                throw contractMismatch("snapshot waiting_user confirmation", null);
            }
        }
        return snapshot;
    }

    private ApiException serviceUnavailable(String operation) {
        return new ApiException(
                HttpStatus.BAD_GATEWAY,
                "AI_SERVICE_ERROR",
                "third workflow " + operation + "失败，请稍后重试"
        );
    }

    private ApiException contractMismatch(String endpoint, Exception cause) {
        String detail = cause == null || cause.getMessage() == null ? "" : "：" + cause.getMessage();
        return new ApiException(
                HttpStatus.BAD_GATEWAY,
                "THIRD_CONTRACT_MISMATCH",
                "third v1 " + endpoint + " 响应不符合契约" + detail
        );
    }

    private boolean isBlank(String value) {
        return value == null || value.isBlank();
    }
}
