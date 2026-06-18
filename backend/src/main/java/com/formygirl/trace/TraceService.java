package com.formygirl.trace;

import com.formygirl.record.BusinessRepository;
import com.formygirl.thirdclient.ThirdWorkflowClient;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;
import org.springframework.stereotype.Service;

@Service
public class TraceService {
    private final BusinessRepository repository;
    private final ThirdWorkflowClient thirdClient;

    public TraceService(BusinessRepository repository, ThirdWorkflowClient thirdClient) {
        this.repository = repository;
        this.thirdClient = thirdClient;
    }

    // 这个函数聚合记录追踪信息。
    public Map<String, Object> trace(String sessionId, String recordId, String thirdSessionId) {
        Map<String, Object> record = recordId == null || recordId.isBlank() ? Map.of() : repository.record(recordId);
        String resolvedSessionId = sessionId;
        if ((resolvedSessionId == null || resolvedSessionId.isBlank()) && !record.isEmpty()) {
            resolvedSessionId = String.valueOf(record.get("session_id"));
        }
        Map<String, Object> session = resolvedSessionId == null || resolvedSessionId.isBlank() ? Map.of() : repository.requireSession(resolvedSessionId);
        List<Map<String, Object>> messages = resolvedSessionId == null || resolvedSessionId.isBlank() ? List.of() : repository.sessionMessages(resolvedSessionId);
        List<Map<String, Object>> drafts = resolvedSessionId == null || resolvedSessionId.isBlank() ? List.of() : repository.sessionDrafts(resolvedSessionId);
        String resolvedRecordId = recordId;
        if ((resolvedRecordId == null || resolvedRecordId.isBlank()) && !record.isEmpty()) {
            resolvedRecordId = String.valueOf(record.get("id"));
        }
        List<Map<String, Object>> syncs = resolvedRecordId == null || resolvedRecordId.isBlank() ? List.of() : repository.feishuSyncs(resolvedRecordId);
        String resolvedThirdSessionId = firstNonBlank(thirdSessionId, firstThirdId(messages), firstThirdId(drafts), firstThirdId(syncs));
        Map<String, Object> third = Map.of();
        if (resolvedThirdSessionId != null) {
            try {
                third = thirdClient.timeline(resolvedThirdSessionId);
            } catch (Exception exception) {
                third = Map.of("error", exception.getMessage());
            }
        }
        return dto(
                "trace", dto("sessionId", resolvedSessionId, "recordId", resolvedRecordId, "thirdSessionId", resolvedThirdSessionId),
                "session", session,
                "messages", messages,
                "drafts", drafts,
                "record", record,
                "display", resolvedRecordId == null ? Map.of() : repository.display(resolvedRecordId),
                "feishuSyncs", syncs,
                "thirdWorkflows", third,
                "issues", List.of()
        );
    }

    // 这个函数找到列表中的第一个 thirdSessionId。
    private String firstThirdId(List<Map<String, Object>> rows) {
        for (Map<String, Object> row : rows) {
            Object value = row.get("third_session_id");
            if (value != null && !String.valueOf(value).isBlank()) {
                return String.valueOf(value);
            }
        }
        return null;
    }

    // 这个函数返回第一个非空字符串。
    private String firstNonBlank(String... values) {
        for (String value : values) {
            if (value != null && !value.isBlank()) {
                return value;
            }
        }
        return null;
    }

    // 这个函数创建允许空值的 DTO Map。
    private Map<String, Object> dto(Object... entries) {
        Map<String, Object> result = new LinkedHashMap<>();
        for (int index = 0; index + 1 < entries.length; index += 2) {
            result.put(String.valueOf(entries[index]), entries[index + 1]);
        }
        return result;
    }
}
