package com.formygirl.thirdclient;

import com.formygirl.common.ApiException;
import com.formygirl.common.AppProperties;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;
import org.springframework.http.HttpStatus;
import org.springframework.stereotype.Component;
import org.springframework.web.client.RestClient;

@Component
public class ThirdWorkflowClient {
    private final RestClient restClient;
    private final AppProperties properties;

    public ThirdWorkflowClient(RestClient restClient, AppProperties properties) {
        this.restClient = restClient;
        this.properties = properties;
    }

    // 这个函数提交 workflow 并轮询到终态或等待确认态。
    public Map<String, Object> invokeAndWait(String text, Map<String, Object> metadata) {
        return invokeAndWait(text, metadata, Map.of());
    }

    // 这个函数提交 workflow，并把敏感上下文放入 third 私有 metadata。
    public Map<String, Object> invokeAndWait(String text, Map<String, Object> metadata, Map<String, Object> privateMetadata) {
        Map<String, Object> created = invoke(text, metadata, privateMetadata);
        String sessionId = String.valueOf(created.get("session_id"));
        return waitFor(sessionId);
    }

    // 这个函数确认 waiting_user workflow 并继续轮询。
    public Map<String, Object> resumeAndWait(String thirdSessionId, String confirmationId, String text) {
        return resumeAndWait(thirdSessionId, confirmationId, text, true);
    }

    // 这个函数按用户选择确认或拒绝 waiting_user workflow 并继续轮询。
    public Map<String, Object> resumeAndWait(String thirdSessionId, String confirmationId, String text, boolean approved) {
        restClient.post()
                .uri(properties.getThirdBaseUrl() + "/workflows/{sessionId}/resume", thirdSessionId)
                .body(Map.of("confirmation_id", confirmationId, "approved", approved, "content", List.of(Map.of("text", text))))
                .retrieve()
                .body(Map.class);
        return waitFor(thirdSessionId);
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
    private Map<String, Object> invoke(String text, Map<String, Object> metadata, Map<String, Object> privateMetadata) {
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

    // 这个函数等待 workflow 进入 success、failed、cancelled 或 waiting_user。
    private Map<String, Object> waitFor(String thirdSessionId) {
        Map<String, Object> response = Map.of("session_id", thirdSessionId, "status", "queued");
        int attempts = Math.max(1, properties.getThirdPollTimes());
        for (int index = 0; index < attempts; index++) {
            response = get(thirdSessionId);
            String status = String.valueOf(response.get("status"));
            if ("success".equals(status) || "failed".equals(status) || "cancelled".equals(status) || "waiting_user".equals(status)) {
                return response;
            }
            sleep();
        }
        return response;
    }

    // 这个函数查询 workflow 当前状态。
    private Map<String, Object> get(String thirdSessionId) {
        try {
            return restClient.get()
                    .uri(properties.getThirdBaseUrl() + "/workflows/{sessionId}", thirdSessionId)
                    .retrieve()
                    .body(Map.class);
        } catch (Exception exception) {
            throw new ApiException(HttpStatus.BAD_GATEWAY, "AI_SERVICE_ERROR", "third workflow 查询失败：" + exception.getMessage());
        }
    }

    // 这个函数在轮询间隔内短暂等待。
    private void sleep() {
        try {
            Thread.sleep(Math.max(50, properties.getThirdPollIntervalMs()));
        } catch (InterruptedException exception) {
            Thread.currentThread().interrupt();
        }
    }
}
