package com.formygirl.thirdclient;

import com.formygirl.common.ApiException;
import com.formygirl.common.AppProperties;
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
        Map<String, Object> created = invoke(text, metadata);
        String sessionId = String.valueOf(created.get("session_id"));
        return waitFor(sessionId);
    }

    // 这个函数确认 waiting_user workflow 并继续轮询。
    public Map<String, Object> resumeAndWait(String thirdSessionId, String confirmationId, String text) {
        restClient.post()
                .uri(properties.getThirdBaseUrl() + "/workflows/{sessionId}/resume", thirdSessionId)
                .body(Map.of("confirmation_id", confirmationId, "approved", true, "content", List.of(Map.of("text", text))))
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

    // 这个函数查询 workflow 时间线摘要。
    public Map<String, Object> timeline(String thirdSessionId) {
        return restClient.get()
                .uri(properties.getThirdBaseUrl() + "/internal/workflows/{sessionId}/timeline", thirdSessionId)
                .retrieve()
                .body(Map.class);
    }

    // 这个函数提交 workflow。
    private Map<String, Object> invoke(String text, Map<String, Object> metadata) {
        try {
            return restClient.post()
                    .uri(properties.getThirdBaseUrl() + "/workflows/invoke")
                    .body(Map.of("content", List.of(Map.of("text", text)), "metadata", metadata))
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
