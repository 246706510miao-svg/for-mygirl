package com.formygirl.feishu;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertThrows;

import com.formygirl.common.ApiException;
import org.junit.jupiter.api.Test;

class FeishuTableUrlParserTest {
    private final FeishuTableUrlParser parser = new FeishuTableUrlParser();

    @Test
    void parsesFeishuBaseTableUrl() {
        FeishuTableUrlParser.ParsedTableUrl parsed = parser.parse("https://example.feishu.cn/base/app_xxx?table=tbl_xxx&view=vew_xxx");

        assertEquals("app_xxx", parsed.appToken());
        assertEquals("tbl_xxx", parsed.tableId());
        assertEquals("vew_xxx", parsed.viewId());
    }

    @Test
    void parsesLarksuiteUrlAndQueryAliases() {
        FeishuTableUrlParser.ParsedTableUrl parsed = parser.parse("https://example.larksuite.com/base/app_yyy?table_id=tbl_yyy&view_id=vew_yyy");

        assertEquals("app_yyy", parsed.appToken());
        assertEquals("tbl_yyy", parsed.tableId());
        assertEquals("vew_yyy", parsed.viewId());
    }

    @Test
    void rejectsUrlWithoutTableId() {
        ApiException exception = assertThrows(ApiException.class, () -> parser.parse("https://example.feishu.cn/base/app_xxx?view=vew_xxx"));

        assertEquals("FEISHU_URL_INVALID", exception.getCode());
    }
}
