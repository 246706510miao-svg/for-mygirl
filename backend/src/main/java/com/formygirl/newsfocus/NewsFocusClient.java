package com.formygirl.newsfocus;

import com.formygirl.common.AppProperties;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;
import org.springframework.stereotype.Component;
import org.springframework.web.client.RestClient;

@Component
public class NewsFocusClient {
    private final RestClient restClient;
    private final AppProperties properties;

    public NewsFocusClient(RestClient restClient, AppProperties properties) {
        this.restClient = restClient;
        this.properties = properties;
    }

    // 这个函数调用 Docker 内部的 third 每日热门生成接口。
    public Map<String, Object> generate(List<String> recentFingerprints) {
        Map<String, Object> body = new LinkedHashMap<>();
        body.put("recentFingerprints", recentFingerprints == null ? List.of() : recentFingerprints);
        body.put("hours", 24);
        Map<String, Object> response = restClient.post()
                .uri(properties.getThirdBaseUrl() + "/internal/news-focus/generate")
                .body(body)
                .retrieve()
                .body(Map.class);
        return response == null ? Map.of() : response;
    }
}
