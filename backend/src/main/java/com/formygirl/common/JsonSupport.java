package com.formygirl.common;

import com.fasterxml.jackson.core.type.TypeReference;
import com.fasterxml.jackson.databind.ObjectMapper;
import com.fasterxml.jackson.databind.JsonNode;
import java.util.List;
import java.util.Map;
import org.springframework.stereotype.Component;

@Component
public class JsonSupport {
    private final ObjectMapper objectMapper;

    public JsonSupport(ObjectMapper objectMapper) {
        this.objectMapper = objectMapper;
    }

    // 这个函数把对象序列化成数据库 JSON 字符串。
    public String stringify(Object value) {
        try {
            return objectMapper.writeValueAsString(value);
        } catch (Exception exception) {
            throw new ApiException(org.springframework.http.HttpStatus.INTERNAL_SERVER_ERROR, "INTERNAL_ERROR", exception.getMessage());
        }
    }

    // 这个函数把数据库 JSON 字符串解析成 Map。
    public Map<String, Object> map(String json) {
        try {
            if (json == null || json.isBlank() || "null".equalsIgnoreCase(json.trim())) {
                return Map.of();
            }
            Map<String, Object> value = objectMapper.readValue(json, new TypeReference<Map<String, Object>>() {});
            return value == null ? Map.of() : value;
        } catch (Exception exception) {
            return Map.of("raw", json);
        }
    }

    // 这个函数把开放 JSON 叶子转换成业务层使用的 Map。
    public Map<String, Object> map(JsonNode value) {
        if (value == null || value.isNull() || !value.isObject()) {
            return Map.of();
        }
        return objectMapper.convertValue(value, new TypeReference<Map<String, Object>>() {});
    }

    // 这个函数把动态飞书字段等开放结构限制在 JsonNode 叶子。
    public JsonNode node(Object value) {
        return objectMapper.valueToTree(value == null ? Map.of() : value);
    }

    // 这个函数把数据库 JSON 字符串解析成 List。
    public List<Object> list(String json) {
        try {
            if (json == null || json.isBlank() || "null".equalsIgnoreCase(json.trim())) {
                return List.of();
            }
            List<Object> value = objectMapper.readValue(json, new TypeReference<List<Object>>() {});
            return value == null ? List.of() : value;
        } catch (Exception exception) {
            return List.of(json);
        }
    }
}
