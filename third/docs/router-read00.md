# Router 到 Read 工作流程

## 1. 输入

输入是用户自然语言，例如：

```json
{
  "input": "查询状态为进行中的记录，只返回标题、状态、截止时间"
}
```

这一步只要求用户说明想查什么，不要求用户在本地配置字段名。

## 2. 字段上下文读取

图先执行 `load_table_fields` 节点。

输入：

```json
{
  "app_token": "来自 THIRD_FEISHU_APP_TOKEN",
  "table_id": "来自 THIRD_FEISHU_TABLE_ID"
}
```

输出：

```json
{
  "table_fields": {
    "source": "feishu",
    "field_names": ["真实字段 A", "真实字段 B"],
    "fields": [
      {
        "field_id": "fld_xxx",
        "field_name": "真实字段 A",
        "type": 1
      }
    ]
  }
}
```

说明：这一步从飞书多维表格读取真实字段列表，后续 Router 只能基于这些字段组织查询。

## 3. Router Agent

Router Agent 接收用户输入和 `table_fields`。

输入：

```json
{
  "input": "用户自然语言",
  "table_fields": {
    "field_names": ["真实字段 A", "真实字段 B"]
  }
}
```

输出：

```json
{
  "route": {
    "intent": "read",
    "target_service": "feishu_bitable",
    "available_table_fields": ["真实字段 A", "真实字段 B"]
  },
  "read_request": {
    "operation": "search_records",
    "field_names": [],
    "filter": {
      "conjunction": "and",
      "conditions": []
    },
    "sort": []
  }
}
```

说明：如果用户没有明确说真实字段名，`field_names` 可以为空，表示让 Read Agent 读取全部字段；Router 不再使用本地默认字段去猜真实表。

## 4. Read Agent

Read Agent 接收 Router 输出的 `read_request` 和前置读取到的 `table_fields`。

输入：

```json
{
  "read_request": {
    "operation": "search_records",
    "field_names": [],
    "filter": {
      "conditions": []
    }
  },
  "table_fields": {
    "field_names": ["真实字段 A", "真实字段 B"]
  }
}
```

输出：

```json
{
  "read_result": {
    "backend": "feishu",
    "record_count": 1,
    "records": [
      {
        "record_id": "rec_xxx",
        "fields": {
          "真实字段 A": "字段值"
        }
      }
    ],
    "warnings": []
  }
}
```

说明：Read Agent 会再次校验字段，避免把不存在的字段传给飞书，最终返回真实记录内容。

## 5. 最终输出

最终输出是 `Read Agent 输出` 文本和结构化 `read_result`。

简短流程：

```text
用户自然语言 -> 读取真实表字段 -> Router 整理读取请求 -> Read 查询飞书记录 -> 返回字段内容
```

