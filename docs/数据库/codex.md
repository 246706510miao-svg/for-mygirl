# 数据库模块 Codex 入口

本文件是 `docs/数据库` 的主入口。Codex 需要设计表结构、写迁移、判断字段归属、实现查询或处理记录状态时，先读这里。

## 这个模块解决什么问题

- 一次日常记录从输入、草稿、确认、飞书同步到首页展示分别落在哪些表。
- 哪些表是 MVP 必须实现，哪些可以后置。
- 状态字段、关系和关键数据不变量是什么。
- 业务数据库与外部配置、飞书、AI、ASR 的边界在哪里。

## 核心数据流

```text
APP_PERSON
  -> RECORD_SESSION
  -> RECORD_MESSAGE
  -> RECORD_DRAFT
  -> DAILY_RECORD
  -> RECORD_DISPLAY
  -> 用户端最近记录展示
```

飞书同步链路：

```text
DAILY_RECORD
  -> FEISHU_SYNC
  -> 飞书文档或多维表格
```

每日内容链路：

```text
DAILY_CONTENT
  -> GET /api/user/home
  -> 用户端首页、记录页、最近记录区域
```

## 表分组

| 分组 | 表 | 作用 |
|---|---|---|
| 身份 | APP_PERSON | 保存用户、管理员等系统使用者 |
| 记录过程 | RECORD_SESSION | 一次对话式记录过程 |
| 记录过程 | RECORD_MESSAGE | 用户文本、语音识别文本、修改指令、AI 或系统消息 |
| 记录过程 | RECORD_DRAFT | AI 每次生成或修改后的草稿版本 |
| 正式记录 | DAILY_RECORD | 用户确认后的正式记录 |
| 展示数据 | RECORD_DISPLAY | 用户端首页和最近记录真正读取的本地展示数据 |
| 每日内容 | DAILY_CONTENT | 管理员配置的每日提示、主题、引导、卡片、提醒 |
| 资源元信息 | RESOURCE_FILE | 文件元信息；MVP 默认不做真实文件上传 |
| 外部同步 | FEISHU_SYNC | 飞书写入 payload、同步状态、错误原因、重试次数 |
| 非敏感配置 | APP_CONFIG | 飞书 Schema、Prompt、展示配置、MCP Payload 规范 |

## MVP 表优先级

第一阶段必须覆盖完整记录闭环：

- APP_PERSON
- RECORD_SESSION
- RECORD_MESSAGE
- RECORD_DRAFT
- DAILY_RECORD
- FEISHU_SYNC
- DAILY_CONTENT
- RECORD_DISPLAY

第二阶段或按需再补：

- APP_CONFIG：当 Prompt、飞书 Schema、展示配置需要后台可维护时再落库；密钥仍然不能入库。
- RESOURCE_FILE：ER 图里已有，但接口 MVP 暂不支持上传背景图、上传照片或长期保存语音音频；没有真实文件能力时不要提前实现复杂存储。

## 关键关系

- 一个 APP_PERSON 可以有多次 RECORD_SESSION。
- 一次 RECORD_SESSION 可以包含多条 RECORD_MESSAGE。
- 一次 RECORD_SESSION 可以产生多个 RECORD_DRAFT。
- 一次 RECORD_SESSION 最终最多确认成一条 DAILY_RECORD。
- DAILY_RECORD 指向最终确认的 RECORD_DRAFT。
- DAILY_RECORD 必须有本地展示数据 RECORD_DISPLAY，至少要能表达成功、失败或异常状态。
- DAILY_RECORD 可以对应多条 FEISHU_SYNC，用于首次写入和后续重试。
- DAILY_CONTENT 面向某个 target_user 和 content_date 生效。

## 状态值基准

### RECORD_SESSION.status

- `editing`：用户正在输入或继续修改。
- `previewing`：已有 AI 草稿预览，等待用户继续修改或确认。
- `confirming`：用户已确认，后端正在锁定草稿、生成 payload 或同步飞书。
- `confirmed`：确认流程结束，已形成正式记录。
- `cancelled`：用户放弃本次记录。

### RECORD_DRAFT.status

- `active`：当前有效草稿。
- `replaced`：已被新草稿替代。
- `confirmed`：被用户最终确认。

### DAILY_RECORD.status

- `success`：本地记录和飞书同步都成功。
- `sync_failed`：本地记录已保存，但飞书同步失败，可重试。
- `blocked`：Payload 校验、安全或权限异常，不能自动写入。

### FEISHU_SYNC.sync_status

- `pending`：准备写入或等待执行。
- `success`：飞书写入成功。
- `failed`：飞书写入失败。

## 数据不变量

- 每次用户文本、语音识别结果、修改指令都要保存为 RECORD_MESSAGE。
- 每次 AI 生成或修改草稿都要保存为新的 RECORD_DRAFT，不能只覆盖旧草稿。
- RECORD_SESSION.current_draft_id 必须指向当前草稿。
- 用户确认时必须锁定一个明确的 RECORD_DRAFT。
- confirm 必须根据 `clientConfirmId` 做幂等；实现时需要在 DAILY_RECORD、RECORD_SESSION 或专门幂等记录中持久化该客户端确认 ID，并建立唯一约束。
- 重复 confirm 不能创建多条 DAILY_RECORD，不能重复写入飞书。
- 飞书失败不能丢本地记录，必须保存 DAILY_RECORD、FEISHU_SYNC.payload_json、错误原因和展示状态。
- AI 生成的 MCP Payload 必须经过后端校验后才能写入 FEISHU_SYNC 并调用飞书 MCP。
- 敏感密钥不进入 APP_CONFIG，放外部配置文件或环境变量。

## API 到表的对应关系

| API | 主要读写表 | 说明 |
|---|---|---|
| `GET /api/user/home` | DAILY_CONTENT、RECORD_DISPLAY、DAILY_RECORD | 首页不直接读飞书 |
| `POST /api/record-sessions` | RECORD_SESSION | 创建记录会话 |
| `POST /api/record-sessions/{sessionId}/messages` | RECORD_SESSION、RECORD_MESSAGE、RECORD_DRAFT | 文本和修改指令统一入口 |
| `POST /api/record-sessions/{sessionId}/voice-messages` | RECORD_SESSION、RECORD_MESSAGE、RECORD_DRAFT | 保存 `asr_text`，不长期保存音频 |
| `GET /api/record-sessions/{sessionId}` | RECORD_SESSION、RECORD_MESSAGE、RECORD_DRAFT | 查询当前会话和草稿 |
| `POST /api/record-sessions/{sessionId}/confirm` | RECORD_SESSION、RECORD_DRAFT、DAILY_RECORD、FEISHU_SYNC、RECORD_DISPLAY | 幂等确认和飞书同步 |
| `POST /api/record-sessions/{sessionId}/cancel` | RECORD_SESSION | 取消会话 |
| `GET /api/admin/records` | DAILY_RECORD、FEISHU_SYNC、RECORD_DISPLAY | 管理员列表和异常筛选 |
| `GET /api/admin/records/{recordId}` | DAILY_RECORD、FEISHU_SYNC、RECORD_DISPLAY、RECORD_DRAFT | 管理员详情 |
| `GET /api/admin/daily-contents` | DAILY_CONTENT | 查询每日内容 |
| `PUT /api/admin/daily-contents` | DAILY_CONTENT | 保存每日内容 |
| `POST /api/admin/records/{recordId}/retry-sync` | DAILY_RECORD、FEISHU_SYNC、RECORD_DISPLAY | 重试飞书同步 |
| `PATCH /api/admin/records/{recordId}/display` | RECORD_DISPLAY | 更新用户端展示，不直接改飞书 |

## 实现提示

- 如果使用关系型数据库，所有外键字段应建立索引，`session_id + version_no` 应唯一。
- `clientMessageId` 和 `clientConfirmId` 建议持久化，避免前端重试导致重复消息、重复草稿或重复正式记录。
- `payload_json`、`draft_json`、`display_json`、`content_json`、`tags_json` 可以使用数据库 JSON 类型；没有 JSON 类型时再退化为 text。
- `record_date`、`content_date` 使用日期类型；时间字段统一使用服务端时间。
- `retry_count` 要有限制，不能通过数据库状态驱动无限重试。

## 文件索引

| 文件 | 什么时候读 | 重点 |
|---|---|---|
| [数据库说明.md](./数据库说明.md) | 需要完整表说明和字段含义时 | 表用途、字段解释、MVP 优先级 |
| [ER图.mermaid](./ER图.mermaid) | 需要看关系结构时 | 表关系、PK、FK、核心字段 |
| [codex.md](./codex.md) | Codex 快速判断和实现时 | 本模块权威入口 |

## 相关模块入口

- 架构边界看 [../架构图/codex.md](../架构图/codex.md)。
- API 合同看 [../接口定义/codex.md](../接口定义/codex.md)。
- 确认写入和异常重试顺序看 [../序列图/04_用户确认写入飞书序列图.mermaid](../序列图/04_用户确认写入飞书序列图.mermaid) 与 [../序列图/07_管理员查看和处理异常序列图.mermaid](../序列图/07_管理员查看和处理异常序列图.mermaid)。
