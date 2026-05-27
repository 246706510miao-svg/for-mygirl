# 接口定义模块 Codex 入口

本文件是 `docs/接口定义` 的主入口。Codex 需要实现 Controller、前端 API Client、接口 Mock、DTO 或接口测试时，先读这里。

## 这个模块解决什么问题

- MVP 要实现哪些用户端和管理员端 API。
- 每个 API 的业务目的、主要读写表和关键响应字段。
- 对话式记录、语音、确认写入、每日内容、异常重试的接口边界。
- 哪些接口必须幂等，哪些响应必须返回 `chatReply` 或 `displayRecord`。

## 全局接口规则

- 所有外部服务调用都经过 Spring Boot 后端，前端只调用 `/api/**`。
- 用户端与对话相关的接口必须返回 `chatReply`，方便前端在对话流里展示反馈。
- AI 草稿每次生成都要返回草稿预览，并保存为 RECORD_DRAFT。
- confirm 必须使用 `clientConfirmId` 做幂等控制。
- 文本消息和修改指令共用 `POST /api/record-sessions/{sessionId}/messages`。
- 语音接口只接收临时音频并返回 `asrText`，MVP 不长期保存音频文件。
- 首页展示不读飞书，数据来自 DAILY_CONTENT、RECORD_DISPLAY、DAILY_RECORD。
- 飞书同步失败时，接口仍要返回本地保存结果和失败状态。

## 用户端 API

| API | 目的 | 必须返回或保证 |
|---|---|---|
| `GET /api/user/home?date=YYYY-MM-DD` | 获取首页每日内容和最近记录 | `dailyContent`、`recentRecords`；不直接读飞书 |
| `POST /api/record-sessions` | 创建记录会话 | `sessionId`、`status=editing` |
| `POST /api/record-sessions/{sessionId}/messages` | 提交文本或修改指令并生成草稿 | `messageId`、`draftId`、`draftVersion`、`previewText`、`draftJson`、`chatReply` |
| `POST /api/record-sessions/{sessionId}/voice-messages` | 提交临时音频，ASR 后生成草稿 | `asrText`、草稿信息、`chatReply` |
| `GET /api/record-sessions/{sessionId}` | 查询当前会话、历史消息和当前草稿 | `messages`、`currentDraft`、`status` |
| `POST /api/record-sessions/{sessionId}/confirm` | 用户确认草稿并写入飞书 | 幂等；返回 `recordId`、`syncStatus`、`chatReply`、`displayRecord` |
| `POST /api/record-sessions/{sessionId}/cancel` | 放弃会话 | `status=cancelled` |

## 管理员端 API

| API | 目的 | 必须返回或保证 |
|---|---|---|
| `GET /api/admin/records?status=&date=` | 查询记录列表或异常记录 | 记录摘要、评分、业务状态、同步状态 |
| `GET /api/admin/records/{recordId}` | 查询记录详情 | 正式文本、摘要、标签、状态、飞书错误信息 |
| `GET /api/admin/daily-contents?targetUserId=&date=` | 查询每日内容配置 | 返回指定用户、日期的配置 |
| `PUT /api/admin/daily-contents` | 保存每日内容配置 | 支持文字、主题、预设背景、引导、卡片、提醒 |
| `POST /api/admin/records/{recordId}/retry-sync` | 重试异常记录的飞书同步 | 修正次数有限；更新 FEISHU_SYNC、DAILY_RECORD、RECORD_DISPLAY |
| `PATCH /api/admin/records/{recordId}/display` | 更新用户端展示内容 | 只改 RECORD_DISPLAY，不直接改飞书 |

## 关键接口细节

### `POST /api/record-sessions/{sessionId}/messages`

用于用户新增文本内容或继续修改草稿。

请求至少包含：

```json
{
  "clientMessageId": "msg_client_001",
  "messageType": "text",
  "content": "今天上午工作有点卡，下午把登录功能调通了"
}
```

`messageType` 可为：

- `text`：新增记录内容。
- `modify`：对当前草稿做修改。

后端必须：

- 保存 RECORD_MESSAGE。
- 读取历史消息和当前草稿。
- 调用 AI 生成新的 RECORD_DRAFT。
- 更新 RECORD_SESSION.current_draft_id。
- 返回 `chatReply` 和最新草稿。

### `POST /api/record-sessions/{sessionId}/voice-messages`

用于语音输入。

请求为 `multipart/form-data`，字段：

- `audio`：临时音频文件。
- `clientMessageId`：前端生成的消息 ID。
- `language`：可选，例如 `zh-CN`。

后端必须：

- 调用 ASR 得到 `asrText`。
- 保存 RECORD_MESSAGE.content 和 `asr_text`。
- 按文本输入流程生成 RECORD_DRAFT。
- 不长期保存音频文件。

### `POST /api/record-sessions/{sessionId}/confirm`

用于用户确认某个草稿并写入飞书。

请求至少包含：

```json
{
  "draftId": "draft_004",
  "clientConfirmId": "confirm_001"
}
```

后端必须：

- 使用 `clientConfirmId` 做幂等，重复提交返回同一正式记录结果。
- 锁定 RECORD_SESSION 和被确认的 RECORD_DRAFT。
- 创建 DAILY_RECORD。
- 让 AI 基于最终草稿和飞书 Schema 生成 MCP Payload。
- 校验目标位置、字段、类型、必填项、权限和安全风险。
- Payload 校验失败时最多让 AI 修正 2 次。
- 成功或失败都保存 FEISHU_SYNC。
- 更新 DAILY_RECORD 和 RECORD_DISPLAY。
- 返回 `chatReply` 和 `displayRecord`。

### `POST /api/admin/records/{recordId}/retry-sync`

用于管理员处理 `sync_failed` 记录。

后端必须：

- 读取 DAILY_RECORD 和最近一次 FEISHU_SYNC.payload_json。
- 判断 payload 是否可直接重试。
- 必要时让 AI 根据错误原因修正 payload。
- 修正次数最多 1 到 2 次。
- 每次失败都更新错误原因和 `retry_count`。
- 不能无限递归重试。

## 状态值基准

| 字段 | 合法值 |
|---|---|
| RECORD_SESSION.status | `editing`、`previewing`、`confirming`、`confirmed`、`cancelled` |
| DAILY_RECORD.status | `success`、`sync_failed`、`blocked` |
| FEISHU_SYNC.sync_status | `pending`、`success`、`failed` |

飞书同步失败统一用 `sync_failed`，不要新增 `feishu_failed`。

## MVP 不做

- 上传背景图、上传照片、服务器文件存储。
- 长期保存语音音频。
- 前端直连 AI、ASR、飞书 MCP。
- 复杂多用户权限系统。
- 管理员统计图表。
- 飞书内容直接预览。
- 多服务器部署、消息队列。

## 推荐实现顺序

1. `POST /api/record-sessions`
2. `POST /api/record-sessions/{sessionId}/messages`，AI 可先 mock
3. `GET /api/record-sessions/{sessionId}`
4. `POST /api/record-sessions/{sessionId}/confirm`，飞书可先 mock
5. `GET /api/user/home`
6. 接入真实飞书 MCP
7. `POST /api/record-sessions/{sessionId}/voice-messages`
8. 管理员每日内容配置
9. 管理员异常列表和 retry-sync

## 文件索引

| 文件 | 什么时候读 | 重点 |
|---|---|---|
| [接口定义说明.md](./接口定义说明.md) | 需要完整请求/响应样例时 | 用户端和管理员端 API 详情 |
| [codex.md](./codex.md) | Codex 快速实现接口时 | 本模块权威入口 |
| [codex_接口实现约束.md](./codex_接口实现约束.md) | 旧版约束参考 | 若与本文件冲突，以本文件为准 |

## 相关模块入口

- 数据库表和字段看 [../数据库/codex.md](../数据库/codex.md)。
- 系统边界看 [../架构图/codex.md](../架构图/codex.md)。
- 交互顺序看 [../序列图/codex_序列图实现约束.md](../序列图/codex_序列图实现约束.md)。
