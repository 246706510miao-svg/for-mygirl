# finagent 到飞书 CRUD Tool 工作流程

## 1. 用户输入

LangGraph 接收的输入只使用 `content[0].text`。

```json
{
  "content": [
    {
      "text": "新增一条记录，标题为测试新增，状态为进行中"
    }
  ]
}
```

说明：用户输入仍然是自然语言。

## 2. finagent 决策

finagent 接收用户输入后，只能做两类动作：

- 输出 `tool_call`，调用一个飞书多维表格 Tool。
- 输出 `answer`，作为最终返回。

当前允许的 Tool：

- `tool_ReadFeishuBitable`：读取、查询、搜索记录。
- `tool_CreateFeishuBitableRecord`：新增记录。
- `tool_UpdateFeishuBitableRecord`：更新记录。
- `tool_DeleteFeishuBitableRecord`：删除记录。

调用 Tool 时，finagent 输出仍然包装在 `content[0].text` 中：

```json
{
  "content": [
    {
      "text": "{\"type\":\"tool_call\",\"tool_name\":\"tool_CreateFeishuBitableRecord\",\"content\":[{\"text\":\"{\\\"original_input\\\":\\\"新增一条记录，标题为测试新增，状态为进行中\\\",\\\"create_request\\\":{\\\"operation\\\":\\\"create_record\\\",\\\"service\\\":\\\"feishu_bitable\\\",\\\"fields\\\":{\\\"标题\\\":\\\"测试新增\\\",\\\"状态\\\":\\\"进行中\\\"}}}\"}]}"
    }
  ]
}
```

说明：`tool_call.content[0].text` 是结构化请求 JSON 字符串，不是原始自然语言。

## 3. Tool 输入

所有 Tool 的输入和输出都使用 `content[0].text` 外壳。

读取请求使用 `read_request`：

```json
{
  "original_input": "查询状态为进行中的记录",
  "read_request": {
    "operation": "search_records",
    "service": "feishu_bitable",
    "field_names": [],
    "filter": {
      "conjunction": "and",
      "conditions": [
        {
          "field_name": "状态",
          "operator": "is",
          "value": "进行中"
        }
      ]
    },
    "sort": [],
    "page_size": 20
  }
}
```

新增请求使用 `create_request`：

```json
{
  "original_input": "新增一条记录，标题为测试新增，状态为进行中",
  "create_request": {
    "operation": "create_record",
    "service": "feishu_bitable",
    "fields": {
      "标题": "测试新增",
      "状态": "进行中"
    }
  }
}
```

更新请求使用 `update_request`：

```json
{
  "original_input": "把标题为测试新增的状态改成已完成",
  "update_request": {
    "operation": "update_record",
    "service": "feishu_bitable",
    "record_id": null,
    "lookup": {
      "filter": {
        "conjunction": "and",
        "conditions": [
          {
            "field_name": "标题",
            "operator": "is",
            "value": "测试新增"
          }
        ]
      }
    },
    "fields": {
      "状态": "已完成"
    }
  }
}
```

删除请求使用 `delete_request`：

```json
{
  "original_input": "删除 record_id 为 recxxx 的记录",
  "delete_request": {
    "operation": "delete_record",
    "service": "feishu_bitable",
    "record_id": "recxxx"
  }
}
```

说明：更新和删除必须通过 `record_id` 或 `lookup.filter` 唯一定位一条记录；定位到 0 条或多条时不会执行写入。

## 4. Tool 输出

Tool 不会作为最终返回；它只把结构化结果交回 finagent。

```json
{
  "content": [
    {
      "text": "{\"type\":\"tool_result\",\"tool_name\":\"tool_CreateFeishuBitableRecord\",\"operation\":\"create_record\",\"record_count\":1,\"record\":{\"record_id\":\"rec_xxx\",\"fields\":{\"标题\":\"测试新增\",\"状态\":\"进行中\"}}}"
    }
  ]
}
```

说明：真实飞书模式下，Tool 会先读取表字段并校验字段名和值；字段不存在或复杂字段无法自动转换时，会把错误写入 `tool_result.error`。

## 5. finagent 最终返回

finagent 接收 tool result 后，总结为最终答案。最终输出仍然只使用 `content[0].text`。

```json
{
  "content": [
    {
      "text": "新增成功。数据来源：真实飞书多维表格。record_id：rec_xxx"
    }
  ]
}
```

简短流程：

```text
用户 content[0].text -> finagent 决策 -> 飞书 CRUD Tool -> finagent 总结 -> answer content[0].text
```
