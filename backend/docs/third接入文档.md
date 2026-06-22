# backend third 接入文档

本文档给 Codex 和前端对接使用。前端不直接调用 third，也不理解 third artifact key；SpringBoot 调用 third、读取 snapshot、选择展示字段，再把稳定 DTO 返回给前端。

## 后端调用 third

消息入口：

```text
POST /api/record-sessions/{sessionId}/messages
```

后端提交给 third：

```json
{
  "content": [
    {
      "text": "用户原始输入"
    }
  ],
  "metadata": {
    "businessSessionId": "RECORD_SESSION.id",
    "idempotencyKey": "clientMessageId"
  }
}
```

后端必须保存和使用：

| 字段 | 来源 | 用途 |
| --- | --- | --- |
| `businessSessionId` | `RECORD_SESSION.id` | 关联本地记录会话和 third workflow。 |
| `thirdSessionId` | third `session_id` | 轮询、snapshot、resume、trace。 |
| `confirmationId` | third `confirmation.confirmation_id` 或 snapshot `confirmation.confirmationId` | 用户确认或取消时回传 third。 |
| `clientConfirmId` | 后端生成或前端传入 | 本地 `DAILY_RECORD` 幂等。 |

## 后端读取 third snapshot

后端优先调用：

```http
GET /internal/workflows/{thirdSessionId}/snapshot
```

后端消费字段：

| snapshot 字段 | 后端用途 |
| --- | --- |
| `session.status` | 判断 `queued/running/waiting_user/success/failed/cancelled`。 |
| `decision.intent` | 判断 workflow 类型，例如 `create_feishu_record`。 |
| `decision.templateKey` | 调试和 trace。 |
| `confirmation.confirmationId` | 返回前端，供确认/取消。 |
| `confirmation.requestText` | 返回前端，作为确认卡标题。 |
| `confirmation.previewJson` | third 原始确认预览，后端可裁剪后给前端。 |
| `outputs.draft` | 生成或展示本地草稿。 |
| `outputs.writePayload.operation` | 判断是否能落本地记录，例如 `create_record`。 |
| `outputs.writePayload.preview` | 生成确认预览和本地草稿。 |
| `outputs.writeResult` | 写入成功后保存到 `FEISHU_SYNC.payload_json`。 |
| `outputs.finalAnswer` | 普通 AI 回复或最终结果文本。 |
| `artifactsByKey` | trace 和排查，不直接给前端。 |

## 后端给前端的 messages 返回

`POST /api/record-sessions/{sessionId}/messages` 返回：

```json
{
  "session": {
    "id": "session_xxx",
    "status": "editing",
    "currentDraftId": "draft_xxx",
    "createdAt": "2026-06-22T10:00:00",
    "updatedAt": "2026-06-22T10:00:05"
  },
  "userMessage": {
    "id": "msg_xxx",
    "sessionId": "session_xxx",
    "sender": "user",
    "inputType": "text",
    "content": "今天学习了韩语，写到飞书里面去",
    "asrText": null,
    "sequenceNo": 1,
    "createdAt": "2026-06-22T10:00:00"
  },
  "aiMessage": {
    "id": "msg_xxx",
    "sessionId": "session_xxx",
    "sender": "ai",
    "inputType": "text",
    "content": "third 已生成需要确认的操作，请核对后决定是否执行。",
    "asrText": null,
    "sequenceNo": 2,
    "createdAt": "2026-06-22T10:00:05"
  },
  "draft": {
    "id": "draft_xxx",
    "sessionId": "session_xxx",
    "versionNo": 1,
    "status": "active",
    "previewText": "今天学习了韩语",
    "draft": {
      "title": "韩语学习",
      "recordDate": "2026-06-22",
      "summary": "今天学习了韩语",
      "score": 80,
      "tags": ["飞书写入"],
      "suggestion": "已根据 third 的写入预览生成，确认后会继续执行 workflow。"
    },
    "createdAt": "2026-06-22T10:00:05"
  },
  "pendingConfirmation": {
    "status": "waiting_user",
    "thirdSessionId": "sess_xxx",
    "confirmationId": "confirm_xxx",
    "requestText": "确认执行以下飞书写入操作吗？",
    "preview": {
      "record_count": 1,
      "records": [
        {
          "record_id": null,
          "fields": {
            "事项名称": "韩语学习",
            "总结": "今天学习了韩语"
          },
          "lookup": {}
        }
      ]
    },
    "clientConfirmId": "cfid_xxx",
    "draftId": "draft_xxx"
  },
  "thirdStatus": "waiting_user"
}
```

字段规则：

- `draft` 可选。只有 third 输出 `outputs.draft`，或后端能从 `outputs.writePayload.operation=create_record` 生成本地草稿时返回。
- `pendingConfirmation` 可选。只有 third `status=waiting_user` 时返回。
- `pendingConfirmation.preview` 是后端选择后的展示 JSON，优先来自 `outputs.writePayload.preview`，其次来自 `confirmation.previewJson`。
- `thirdStatus` 是 third 当前状态，不等同于 `session.status`。
- third 原始 snapshot 不给前端；只保存到后端 trace 或 `FEISHU_SYNC.payload_json`。

## 前端确认或取消

前端调用：

```text
POST /api/record-sessions/{sessionId}/confirm/resume
```

请求：

```json
{
  "thirdSessionId": "sess_xxx",
  "confirmationId": "confirm_xxx",
  "approved": true,
  "clientConfirmId": "cfid_xxx",
  "draftId": "draft_xxx"
}
```

请求字段：

| 字段 | 必填 | 说明 |
| --- | --- | --- |
| `thirdSessionId` | 是 | third workflow session。 |
| `confirmationId` | 是 | third confirmation ID。 |
| `approved` | 是 | `true` 继续执行，`false` 取消。 |
| `clientConfirmId` | 建议 | 本地确认幂等 ID。没有时后端用 `thirdSessionId + "_confirm"`。 |
| `draftId` | 可选 | 有本地草稿时传；纯查询、字段变更等 workflow 可以为空。 |

返回：

```json
{
  "session": {},
  "record": {},
  "feishuSync": {},
  "display": {},
  "replyMessage": {},
  "draft": {},
  "status": "cancelled",
  "thirdStatus": "success"
}
```

返回规则：

- `approved=false` 时返回 `status=cancelled`，不落 `DAILY_RECORD`。
- `approved=true` 且有 `draftId` 时，成功后落 `DAILY_RECORD`、`RECORD_DISPLAY`、`FEISHU_SYNC`。
- `approved=true` 但没有 `draftId` 时，只返回 third 最终结果和 reply，不伪造本地记录。

## 后端落库规则

- 本地展示字段由后端选择，不由 third 或前端决定。
- `RECORD_DRAFT.draft_json` 保存后端整理后的草稿字段。
- `FEISHU_SYNC.payload_json.thirdSnapshot` 保存 third 原始 snapshot，便于追踪。
- `DAILY_RECORD` 只在后端确认这是本地记录写入时创建。
- 前端最近记录列表只读本地 `DAILY_RECORD` 和 `RECORD_DISPLAY`。
