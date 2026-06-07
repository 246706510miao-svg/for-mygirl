# finagent 到 tool_ReadFeishuBitable 工作流程

## 1. 用户输入

LangGraph 接收的输入只使用 `content[0].text`。

```json
{
  "content": [
    {
      "text": "我的飞书里现在有什么内容"
    }
  ]
}
```

说明：用户输入仍然是自然语言。

## 2. finagent 决策

finagent 接收用户输入后，决定是否调用工具。

当 `THIRD_FINAGENT_USE_LLM=1` 时，finagent 必须由 LLM 输出合法 JSON；LLM 不可用、输出非法或结构不对时直接返回 strict mode 错误，不使用规则兜底。

调用工具时，finagent 输出：

```json
{
  "content": [
    {
      "text": "{\"type\":\"tool_call\",\"tool_name\":\"tool_ReadFeishuBitable\",\"content\":[{\"text\":\"{\\\"original_input\\\":\\\"我的飞书里现在有什么内容\\\",\\\"read_request\\\":{\\\"operation\\\":\\\"search_records\\\",\\\"service\\\":\\\"feishu_bitable\\\",\\\"record_id\\\":null,\\\"field_names\\\":[],\\\"filter\\\":{\\\"conjunction\\\":\\\"and\\\",\\\"conditions\\\":[]},\\\"sort\\\":[],\\\"page_size\\\":20,\\\"page_token\\\":null,\\\"automatic_fields\\\":true}}\"}]}"
    }
  ]
}
```

说明：这里仍然只通过 `content[0].text` 传递信息，文本内容是工具调用 JSON。

## 3. tool_ReadFeishuBitable 输入

工具接收 finagent 的 `content[0].text`，从中取出给工具的 `content[0].text`。

在 strict LLM 模式下，工具输入必须是包含 `read_request` 的 JSON 字符串：

```json
{
  "original_input": "我的飞书里现在有什么内容",
  "read_request": {
    "operation": "search_records",
    "service": "feishu_bitable",
    "record_id": null,
    "field_names": [],
    "filter": {
      "conjunction": "and",
      "conditions": []
    },
    "sort": [],
    "page_size": 20,
    "page_token": null,
    "automatic_fields": true
  }
}
```

说明：`THIRD_FINAGENT_USE_LLM=1` 时，Tool 不会从自然语言里提取字段、过滤、排序或分页；缺少 `read_request` 会返回 `strict_input_validation` 错误。

## 4. tool_ReadFeishuBitable 输出

工具输出仍然只使用 `content[0].text`，文本内容是 tool result JSON。

```json
{
  "content": [
    {
      "text": "{\"type\":\"tool_result\",\"tool_name\":\"tool_ReadFeishuBitable\",\"record_count\":1,\"records\":[{\"record_id\":\"rec_xxx\",\"fields\":{\"标题\":\"示例\",\"状态\":\"进行中\"}}]}"
    }
  ]
}
```

说明：工具不会作为最终返回；它只把读取到的信息交回 finagent。

## 5. finagent 最终返回

finagent 接收 tool result 后，总结为最终答案。

当 `THIRD_FINAGENT_USE_LLM=1` 时，总结也必须由 LLM 完成；LLM 总结失败时返回 strict mode 错误，不使用规则总结。

```json
{
  "content": [
    {
      "text": "查询到 1 条记录：标题为示例，状态为进行中。"
    }
  ]
}
```

简短流程：

```text
用户 content[0].text -> finagent LLM 决策 -> tool_ReadFeishuBitable 读取 -> finagent LLM 总结 -> answer content[0].text
```
