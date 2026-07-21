package com.formygirl.feishu;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertThrows;
import static org.mockito.ArgumentMatchers.any;
import static org.mockito.ArgumentMatchers.eq;
import static org.mockito.Mockito.mock;
import static org.mockito.Mockito.never;
import static org.mockito.Mockito.verify;
import static org.mockito.Mockito.when;

import com.formygirl.common.ApiException;
import com.formygirl.common.JsonSupport;
import com.formygirl.thirdclient.ThirdWorkflowClient;
import com.formygirl.thirdclient.ThirdWorkflowContracts.FeishuTableResolveResponse;
import java.util.LinkedHashMap;
import java.util.Map;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.Test;
import org.mockito.ArgumentCaptor;
import org.springframework.http.HttpStatus;

class FeishuConfigServiceTest {
    private FeishuConfigRepository repository;
    private FeishuSecretCodec secretCodec;
    private ThirdWorkflowClient thirdClient;
    private FeishuConfigService service;

    @BeforeEach
    void setUp() {
        repository = mock(FeishuConfigRepository.class);
        secretCodec = mock(FeishuSecretCodec.class);
        thirdClient = mock(ThirdWorkflowClient.class);
        service = new FeishuConfigService(repository, secretCodec, thirdClient, mock(JsonSupport.class));
        when(repository.account("user_1")).thenReturn(account());
        when(secretCodec.decrypt("secret_cipher")).thenReturn("secret_plain");
        when(secretCodec.decrypt("")).thenReturn("");
    }

    @Test
    void createTablePersistsTheLocationResolvedByThird() {
        String tableUrl = "https://example.feishu.cn/wiki/wik_xxx?table=tbl_xxx&view=vew_xxx";
        when(thirdClient.resolveFeishuTable(eq(tableUrl), any())).thenReturn(
                new FeishuTableResolveResponse(
                        "ok",
                        null,
                        "飞书多维表格 URL 解析成功。",
                        "wiki",
                        "app_from_wiki",
                        "tbl_xxx",
                        "vew_xxx"
                )
        );
        when(repository.insertTable(eq("user_1"), eq("account_1"), eq("每日记录"), eq(tableUrl), any(), any(), eq(true)))
                .thenReturn(tableRow(tableUrl));

        service.createTable(
                "user_1",
                new FeishuConfigService.TableInput("每日记录", tableUrl, true, Map.of())
        );

        ArgumentCaptor<FeishuTableLocation> location = ArgumentCaptor.forClass(FeishuTableLocation.class);
        verify(repository).insertTable(
                eq("user_1"),
                eq("account_1"),
                eq("每日记录"),
                eq(tableUrl),
                location.capture(),
                eq(Map.of()),
                eq(true)
        );
        assertEquals("app_from_wiki", location.getValue().appToken());
        assertEquals("tbl_xxx", location.getValue().tableId());
        assertEquals("vew_xxx", location.getValue().viewId());
    }

    @Test
    void createTableDoesNotWriteWhenThirdRejectsTheWikiNode() {
        String tableUrl = "https://example.feishu.cn/wiki/wik_xxx?table=tbl_xxx";
        when(thirdClient.resolveFeishuTable(eq(tableUrl), any())).thenThrow(
                new ApiException(HttpStatus.BAD_REQUEST, "FEISHU_WIKI_NOT_BITABLE", "该 Wiki 链接指向的不是飞书多维表格。")
        );

        ApiException exception = assertThrows(
                ApiException.class,
                () -> service.createTable(
                        "user_1",
                        new FeishuConfigService.TableInput("每日记录", tableUrl, true, Map.of())
                )
        );

        assertEquals("FEISHU_WIKI_NOT_BITABLE", exception.getCode());
        verify(repository, never()).insertTable(any(), any(), any(), any(), any(), any(), eq(true));
    }

    @Test
    void updateTableDoesNotOverwriteTheExistingLocationWhenResolutionFails() {
        String currentUrl = "https://example.feishu.cn/base/app_old?table=tbl_old";
        String nextUrl = "https://example.feishu.cn/wiki/wik_xxx?table=tbl_xxx";
        when(repository.table("user_1", "table_config_1")).thenReturn(tableRow(currentUrl));
        when(thirdClient.resolveFeishuTable(eq(nextUrl), any())).thenThrow(
                new ApiException(HttpStatus.BAD_REQUEST, "FEISHU_WIKI_PERMISSION_DENIED", "无法读取飞书 Wiki 节点。")
        );

        ApiException exception = assertThrows(
                ApiException.class,
                () -> service.updateTable(
                        "user_1",
                        "table_config_1",
                        new FeishuConfigService.TableInput("每日记录", nextUrl, true, Map.of())
                )
        );

        assertEquals("FEISHU_WIKI_PERMISSION_DENIED", exception.getCode());
        verify(repository, never()).updateTable(any(), any(), any(), any(), any(), any(), eq(true));
    }

    private Map<String, Object> account() {
        Map<String, Object> account = new LinkedHashMap<>();
        account.put("id", "account_1");
        account.put("enabled", true);
        account.put("app_id", "cli_test");
        account.put("app_secret_cipher", "secret_cipher");
        account.put("tenant_access_token_cipher", "");
        account.put("user_id_type", "open_id");
        return account;
    }

    private Map<String, Object> tableRow(String tableUrl) {
        Map<String, Object> row = new LinkedHashMap<>();
        row.put("id", "table_config_1");
        row.put("display_name", "每日记录");
        row.put("table_url", tableUrl);
        row.put("table_id", "tbl_xxx");
        row.put("table_name", "每日记录");
        row.put("view_id", "vew_xxx");
        row.put("is_default", true);
        row.put("enabled", true);
        row.put("field_name_map_json", Map.of());
        return row;
    }
}
