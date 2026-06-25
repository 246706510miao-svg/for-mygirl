package com.formygirl.feishu;

import com.formygirl.common.ApiException;
import java.net.URI;
import java.net.URLDecoder;
import java.nio.charset.StandardCharsets;
import java.util.LinkedHashMap;
import java.util.Map;
import org.springframework.http.HttpStatus;
import org.springframework.stereotype.Component;

@Component
public class FeishuTableUrlParser {
    public ParsedTableUrl parse(String value) {
        if (value == null || value.isBlank()) {
            throw badRequest("请填写飞书多维表格 URL。");
        }
        URI uri = parseUri(value.trim());
        String host = String.valueOf(uri.getHost()).toLowerCase();
        if (!host.endsWith(".feishu.cn") && !host.endsWith(".larksuite.com")) {
            throw badRequest("只支持 feishu.cn 或 larksuite.com 的多维表格 URL。");
        }
        String appToken = appToken(uri.getPath());
        Map<String, String> query = queryParams(uri.getRawQuery());
        String tableId = firstNonBlank(query.get("table"), query.get("table_id"));
        String viewId = firstNonBlank(query.get("view"), query.get("view_id"));
        if (tableId == null || tableId.isBlank()) {
            throw badRequest("飞书 URL 缺少 table 参数，请从具体多维表格视图复制链接。");
        }
        return new ParsedTableUrl(appToken, tableId, viewId == null ? "" : viewId);
    }

    private URI parseUri(String value) {
        try {
            return URI.create(value);
        } catch (IllegalArgumentException exception) {
            throw badRequest("飞书多维表格 URL 格式不正确。");
        }
    }

    private String appToken(String path) {
        String[] segments = String.valueOf(path).split("/");
        for (int index = 0; index + 1 < segments.length; index++) {
            if ("base".equals(segments[index]) && !segments[index + 1].isBlank()) {
                return segments[index + 1];
            }
        }
        throw badRequest("飞书 URL 缺少 /base/{appToken}。");
    }

    private Map<String, String> queryParams(String rawQuery) {
        Map<String, String> result = new LinkedHashMap<>();
        if (rawQuery == null || rawQuery.isBlank()) {
            return result;
        }
        for (String item : rawQuery.split("&")) {
            if (item.isBlank()) {
                continue;
            }
            String[] parts = item.split("=", 2);
            String key = decode(parts[0]);
            String value = parts.length > 1 ? decode(parts[1]) : "";
            result.put(key, value);
        }
        return result;
    }

    private String decode(String value) {
        return URLDecoder.decode(value, StandardCharsets.UTF_8);
    }

    private String firstNonBlank(String... values) {
        for (String value : values) {
            if (value != null && !value.isBlank()) {
                return value;
            }
        }
        return null;
    }

    private ApiException badRequest(String message) {
        return new ApiException(HttpStatus.BAD_REQUEST, "FEISHU_URL_INVALID", message);
    }

    public record ParsedTableUrl(String appToken, String tableId, String viewId) {
    }
}
