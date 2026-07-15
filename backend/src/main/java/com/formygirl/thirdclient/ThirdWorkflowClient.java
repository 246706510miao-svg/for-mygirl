package com.formygirl.thirdclient;

import com.formygirl.common.ApiException;
import com.formygirl.common.AppProperties;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;
import org.springframework.http.HttpStatus;
import org.springframework.stereotype.Component;
import org.springframework.web.client.RestClient;
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
    public Map<String, Object> resume(String thirdSessionId, String confirmationId, String text, boolean approved) {
        return resume(thirdSessionId, confirmationId, text, approved ? "approve" : "cancel", approved);
    }

    // 这个函数提交明确的交互类型，支持追问回答和确认修改。
    public Map<String, Object> resume(String thirdSessionId, String confirmationId, String text, String response, boolean approved) {
        try {
            Map<String, Object> body = new LinkedHashMap<>();
            body.put("confirmation_id", confirmationId);
            body.put("approved", approved);
            body.put("response", response);
            body.put("content", List.of(Map.of("text", text)));
            restClient.post()
                    .uri(properties.getThirdBaseUrl() + "/workflows/{sessionId}/resume", thirdSessionId)
                    .body(body)
                    .retrieve()
                    .body(Map.class);
            return get(thirdSessionId);
        } catch (RestClientResponseException exception) {
            if (exception.getStatusCode().value() == 400 || exception.getStatusCode().value() == 409) {
                throw new ApiException(HttpStatus.CONFLICT, "STALE_INTERACTION", "刚才的问题已经更新，请刷新后继续");
            }
            throw new ApiException(HttpStatus.BAD_GATEWAY, "AI_SERVICE_ERROR", "third workflow 暂时无法继续，请稍后重试");
        } catch (ApiException exception) {
            throw exception;
        } catch (Exception exception) {
            throw new ApiException(HttpStatus.BAD_GATEWAY, "AI_SERVICE_ERROR", "third workflow 暂时无法继续，请稍后重试");
        }
    }

    // 这个函数查询 workflow artifact 明细。
    public Map<String, Object> artifacts(String thirdSessionId) {
        return restClient.get()
                .uri(properties.getThirdBaseUrl() + "/internal/workflows/{sessionId}/artifacts", thirdSessionId)
                .retrieve()
                .body(Map.class);
    }

    // 这个函数查询 workflow 统一快照，供后端按契约消费全量 JSON。
    public Map<String, Object> snapshot(String thirdSessionId) {
        return restClient.get()
                .uri(properties.getThirdBaseUrl() + "/internal/workflows/{sessionId}/snapshot", thirdSessionId)
                .retrieve()
                .body(Map.class);
    }

    // 这个函数查询 workflow 时间线摘要。
    public Map<String, Object> timeline(String thirdSessionId) {
        return restClient.get()
                .uri(properties.getThirdBaseUrl() + "/internal/workflows/{sessionId}/timeline", thirdSessionId)
                .retrieve()
                .body(Map.class);
    }

    // 这个函数让 third 使用私有飞书配置测试表连接。
    public Map<String, Object> checkFeishuTable(Map<String, Object> privateMetadata) {
        try {
            return restClient.post()
                    .uri(properties.getThirdBaseUrl() + "/internal/feishu/table-check")
                    .body(Map.of("privateMetadata", privateMetadata == null ? Map.of() : privateMetadata))
                    .retrieve()
                    .body(Map.class);
        } catch (Exception exception) {
            throw new ApiException(HttpStatus.BAD_GATEWAY, "AI_SERVICE_ERROR", "third 飞书表测试失败：" + exception.getMessage());
        }
    }

    // 这个函数提交 workflow。
    public Map<String, Object> invoke(String text, Map<String, Object> metadata, Map<String, Object> privateMetadata) {
        try {
            Map<String, Object> body = new LinkedHashMap<>();
            body.put("content", List.of(Map.of("text", text)));
            body.put("metadata", metadata == null ? Map.of() : metadata);
            body.put("privateMetadata", privateMetadata == null ? Map.of() : privateMetadata);
            return restClient.post()
                    .uri(properties.getThirdBaseUrl() + "/workflows/invoke")
                    .body(body)
                    .retrieve()
                    .body(Map.class);
        } catch (Exception exception) {
            throw new ApiException(HttpStatus.BAD_GATEWAY, "AI_SERVICE_ERROR", "third workflow 调用失败：" + exception.getMessage());
        }
    }

    // 这个函数查询 workflow 当前状态。
    public Map<String, Object> get(String thirdSessionId) {
        try {
            return restClient.get()
                    .uri(properties.getThirdBaseUrl() + "/workflows/{sessionId}", thirdSessionId)
                    .retrieve()
                    .body(Map.class);
        } catch (Exception exception) {
            throw new ApiException(HttpStatus.BAD_GATEWAY, "AI_SERVICE_ERROR", "third workflow 查询失败：" + exception.getMessage());
        }
    }
}
