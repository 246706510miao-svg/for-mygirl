package com.formygirl.feishu;

import com.formygirl.common.ApiException;
import com.formygirl.common.JsonSupport;
import com.formygirl.thirdclient.ThirdWorkflowContracts.FeishuAccountMetadata;
import com.formygirl.thirdclient.ThirdWorkflowContracts.FeishuPrivateMetadata;
import com.formygirl.thirdclient.ThirdWorkflowContracts.FeishuPublicMetadata;
import com.formygirl.thirdclient.ThirdWorkflowContracts.FeishuTableCheckResponse;
import com.formygirl.thirdclient.ThirdWorkflowContracts.FeishuTableMetadata;
import com.formygirl.thirdclient.ThirdWorkflowContracts.FeishuTableResolveResponse;
import com.formygirl.thirdclient.ThirdWorkflowContracts.WorkflowPrivateMetadata;
import com.formygirl.thirdclient.ThirdWorkflowClient;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;
import org.springframework.http.HttpStatus;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;

@Service
public class FeishuConfigService {
    private final FeishuConfigRepository repository;
    private final FeishuSecretCodec secretCodec;
    private final ThirdWorkflowClient thirdClient;
    private final JsonSupport json;

    public FeishuConfigService(FeishuConfigRepository repository, FeishuSecretCodec secretCodec, ThirdWorkflowClient thirdClient, JsonSupport json) {
        this.repository = repository;
        this.secretCodec = secretCodec;
        this.thirdClient = thirdClient;
        this.json = json;
    }

    public Map<String, Object> account(String userId) {
        return accountDto(repository.account(userId));
    }

    @Transactional
    public Map<String, Object> saveAccount(String userId, AccountInput input) {
        Map<String, Object> current = repository.account(userId);
        String appSecretCipher = preserveOrEncrypt(input.appSecret(), current.get("app_secret_cipher"));
        String tenantTokenCipher = preserveOrEncrypt(input.tenantAccessToken(), current.get("tenant_access_token_cipher"));
        return accountDto(repository.upsertAccount(
                userId,
                input.enabled(),
                input.appId(),
                appSecretCipher,
                tenantTokenCipher,
                input.userIdType()
        ));
    }

    public Map<String, Object> tables(String userId) {
        return Map.of("items", repository.tables(userId).stream().map(this::tableDto).toList());
    }

    @Transactional
    public Map<String, Object> createTable(String userId, TableInput input) {
        Map<String, Object> account = requireAccount(userId);
        String tableUrl = input.tableUrl() == null ? "" : input.tableUrl().trim();
        FeishuTableLocation location = resolveTableLocation(tableUrl, account);
        String displayName = displayName(input.displayName(), location.tableId());
        Map<String, Object> row = repository.insertTable(
                userId,
                String.valueOf(account.get("id")),
                displayName,
                tableUrl,
                location,
                fieldNameMap(input.fieldNameMap()),
                input.enabled()
        );
        return tableDto(row);
    }

    @Transactional
    public Map<String, Object> updateTable(String userId, String tableId, TableInput input) {
        Map<String, Object> current = requireTable(userId, tableId);
        Map<String, Object> account = requireAccount(userId);
        String nextUrl = input.tableUrl() == null || input.tableUrl().isBlank() ? String.valueOf(current.get("table_url")) : input.tableUrl().trim();
        FeishuTableLocation location = resolveTableLocation(nextUrl, account);
        String displayName = displayName(input.displayName(), String.valueOf(current.get("display_name")));
        Map<String, Object> row = repository.updateTable(userId, tableId, displayName, nextUrl, location, fieldNameMap(input.fieldNameMap()), input.enabled());
        return tableDto(row);
    }

    @Transactional
    public Map<String, Object> setDefault(String userId, String tableId) {
        requireTable(userId, tableId);
        return tableDto(repository.setDefault(userId, tableId));
    }

    @Transactional
    public Map<String, Object> testTable(String userId, String tableId) {
        requireTable(userId, tableId);
        WorkflowFeishuContext context = workflowContext(userId, tableId);
        FeishuTableCheckResponse result = thirdClient.checkFeishuTable(context.privateMetadata());
        String status = "ok".equals(result.status()) ? "ok" : "error";
        String message = result.message();
        repository.updateTestStatus(userId, tableId, status, message);
        Map<String, Object> dto = dto(
                "status", result.status(),
                "message", result.message(),
                "tableName", result.tableName(),
                "fieldCount", result.fieldCount(),
                "fieldNames", result.fieldNames()
        );
        dto.put("table", tableDto(repository.table(userId, tableId)));
        return dto;
    }

    public String resolveTableConfigIdForNewSession(String userId, String requestedTableConfigId) {
        if (requestedTableConfigId != null && !requestedTableConfigId.isBlank()) {
            Map<String, Object> table = requireTable(userId, requestedTableConfigId);
            if (!boolValue(table.get("enabled"), true)) {
                throw new ApiException(HttpStatus.CONFLICT, "FEISHU_TABLE_DISABLED", "当前飞书表配置已停用");
            }
            return requestedTableConfigId;
        }
        Map<String, Object> table = repository.defaultTable(userId);
        return table.isEmpty() ? null : String.valueOf(table.get("id"));
    }

    public WorkflowFeishuContext workflowContext(String userId, String tableConfigId) {
        if (tableConfigId == null || tableConfigId.isBlank()) {
            return new WorkflowFeishuContext(null, null, WorkflowPrivateMetadata.empty());
        }
        Map<String, Object> table = requireTable(userId, tableConfigId);
        Map<String, Object> account = repository.account(userId);
        FeishuPublicMetadata safe = new FeishuPublicMetadata(
                stringValue(table.get("id")),
                stringValue(table.get("display_name")),
                stringValue(table.get("table_id")),
                stringValue(table.get("view_id"))
        );
        if (account.isEmpty()) {
            return new WorkflowFeishuContext(tableConfigId, safe, WorkflowPrivateMetadata.empty());
        }
        WorkflowPrivateMetadata privateMetadata = new WorkflowPrivateMetadata(
                new FeishuPrivateMetadata(
                        stringValue(table.get("id")),
                        new FeishuAccountMetadata(
                                boolValue(account.get("enabled"), true),
                                stringValue(account.get("app_id")),
                                secretCodec.decrypt(stringValue(account.get("app_secret_cipher"))),
                                secretCodec.decrypt(stringValue(account.get("tenant_access_token_cipher"))),
                                stringValue(account.get("user_id_type"))
                        ),
                        new FeishuTableMetadata(
                                boolValue(table.get("enabled"), true),
                                stringValue(table.get("display_name")),
                                stringValue(table.get("app_token")),
                                stringValue(table.get("table_id")),
                                stringValue(table.get("table_name")),
                                stringValue(table.get("view_id")),
                                json.node(jsonMap(table.get("field_name_map_json")))
                        )
                )
        );
        return new WorkflowFeishuContext(tableConfigId, safe, privateMetadata);
    }

    private Map<String, Object> requireAccount(String userId) {
        Map<String, Object> account = repository.account(userId);
        if (account.isEmpty()) {
            throw new ApiException(HttpStatus.CONFLICT, "FEISHU_ACCOUNT_REQUIRED", "请先保存飞书应用凭证");
        }
        return account;
    }

    private Map<String, Object> requireTable(String userId, String tableId) {
        Map<String, Object> table = repository.table(userId, tableId);
        if (table.isEmpty()) {
            throw new ApiException(HttpStatus.NOT_FOUND, "FEISHU_TABLE_NOT_FOUND", "飞书表配置不存在");
        }
        return table;
    }

    private FeishuTableLocation resolveTableLocation(String tableUrl, Map<String, Object> account) {
        WorkflowPrivateMetadata privateMetadata = new WorkflowPrivateMetadata(
                new FeishuPrivateMetadata(
                        null,
                        new FeishuAccountMetadata(
                                boolValue(account.get("enabled"), true),
                                stringValue(account.get("app_id")),
                                secretCodec.decrypt(stringValue(account.get("app_secret_cipher"))),
                                secretCodec.decrypt(stringValue(account.get("tenant_access_token_cipher"))),
                                stringValue(account.get("user_id_type"))
                        ),
                        null
                )
        );
        FeishuTableResolveResponse resolved = thirdClient.resolveFeishuTable(tableUrl, privateMetadata);
        return new FeishuTableLocation(resolved.appToken(), resolved.tableId(), resolved.viewId());
    }

    private Map<String, Object> accountDto(Map<String, Object> row) {
        if (row == null || row.isEmpty()) {
            return dto("configured", false, "enabled", true, "appId", "", "appSecretConfigured", false, "tenantAccessTokenConfigured", false, "userIdType", "open_id");
        }
        return dto(
                "configured", true,
                "id", row.get("id"),
                "enabled", row.get("enabled"),
                "appId", stringValue(row.get("app_id")),
                "appSecretConfigured", !stringValue(row.get("app_secret_cipher")).isBlank(),
                "tenantAccessTokenConfigured", !stringValue(row.get("tenant_access_token_cipher")).isBlank(),
                "userIdType", stringValue(row.get("user_id_type")).isBlank() ? "open_id" : row.get("user_id_type"),
                "updatedAt", row.get("updated_at")
        );
    }

    private Map<String, Object> tableDto(Map<String, Object> row) {
        return dto(
                "id", row.get("id"),
                "displayName", row.get("display_name"),
                "tableUrl", row.get("table_url"),
                "tableId", row.get("table_id"),
                "tableName", row.get("table_name"),
                "viewId", row.get("view_id"),
                "isDefault", row.get("is_default"),
                "enabled", row.get("enabled"),
                "fieldNameMap", jsonMap(row.get("field_name_map_json")),
                "lastTestStatus", row.get("last_test_status"),
                "lastTestMessage", row.get("last_test_message"),
                "lastTestAt", row.get("last_test_at"),
                "updatedAt", row.get("updated_at")
        );
    }

    private String preserveOrEncrypt(String rawValue, Object currentCipher) {
        if (rawValue == null || rawValue.isBlank()) {
            return stringValue(currentCipher);
        }
        return secretCodec.encrypt(rawValue.trim());
    }

    private Map<String, Object> fieldNameMap(Map<String, Object> value) {
        return value == null ? Map.of() : value;
    }

    private Map<String, Object> jsonMap(Object value) {
        if (value instanceof Map<?, ?> map) {
            Map<String, Object> result = new LinkedHashMap<>();
            map.forEach((key, item) -> result.put(String.valueOf(key), item));
            return result;
        }
        return json.map(String.valueOf(value));
    }

    private String displayName(String value, String fallback) {
        if (value != null && !value.isBlank()) {
            return value.trim();
        }
        return fallback == null || fallback.isBlank() ? "飞书表" : fallback;
    }

    private boolean boolValue(Object value, boolean fallback) {
        if (value instanceof Boolean bool) {
            return bool;
        }
        if (value == null) {
            return fallback;
        }
        return Boolean.parseBoolean(String.valueOf(value)) || "1".equals(String.valueOf(value));
    }

    private String stringValue(Object value) {
        return value == null ? "" : String.valueOf(value);
    }

    private Map<String, Object> dto(Object... entries) {
        Map<String, Object> result = new LinkedHashMap<>();
        for (int index = 0; index + 1 < entries.length; index += 2) {
            Object value = entries[index + 1];
            if (value != null) {
                result.put(String.valueOf(entries[index]), value);
            }
        }
        return result;
    }

    public record AccountInput(boolean enabled, String appId, String appSecret, String tenantAccessToken, String userIdType) {
    }

    public record TableInput(String displayName, String tableUrl, boolean enabled, Map<String, Object> fieldNameMap) {
    }

    public record WorkflowFeishuContext(
            String tableConfigId,
            FeishuPublicMetadata publicMetadata,
            WorkflowPrivateMetadata privateMetadata
    ) {
    }
}
