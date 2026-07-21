package com.formygirl.feishu;

/** Spring Boot 业务库持久化使用的标准飞书多维表格定位信息。 */
public record FeishuTableLocation(String appToken, String tableId, String viewId) {
}
