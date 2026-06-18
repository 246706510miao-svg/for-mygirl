# 数据库模块 Codex 入口

本文件是 `docs/数据库` 的主入口。Codex 需要设计表结构、写迁移、判断字段归属、实现查询或处理记录状态时，先读这里。

## 这个模块解决什么问题

- 表说明
- 一次日常记录从输入、草稿、确认、飞书同步到首页展示分别落在哪些表。
- 状态字段、关系和关键数据不变量是什么。
- 业务数据库与外部配置、飞书、AI、ASR 的边界在哪里。

## 表说明

### APP_PERSON

保存系统中的使用者。

虽然目前只有用户和管理员两个人，但保留这张表可以让记录归属更清楚。

| 字段 | 说明 |
|---|---|
| id | 主键，人员 ID |
| role | USER 或 OPS_ADMIN；旧 PARTNER、ADMIN 只作为兼容口径 |
| display_name | 显示名称 |
| enabled | 是否启用 |
| created_at | 创建时间 |
| current_view_role | 手机端当前视角：USER、BOUND_ADMIN；OPS_ADMIN 固定为后台人员视角 |

### RECORD_SESSION

保存一次对话式记录过程。

用户还没确认写入之前，文本输入、语音输入、修改指令都属于同一个 session。

| 字段 | 说明 |
|---|---|
| id | 主键，会话 ID |
| user_id | 外键，属于哪个用户 |
| status | editing、previewing、confirmed、cancelled |
| current_draft_id | 当前草稿 ID |
| created_at | 创建时间 |
| updated_at | 更新时间 |

### RECORD_MESSAGE

保存一次记录会话里的消息。

包括：

- 用户文本输入
- 用户语音识别结果
- 用户修改指令
- AI 回复或系统消息

| 字段 | 说明 |
|---|---|
| id | 主键，消息 ID |
| session_id | 外键，属于哪次记录会话 |
| sender | user、ai、system |
| input_type | text、voice |
| content | 消息内容 |
| asr_text | 语音识别后的文本 |
| sequence_no | 消息顺序 |
| created_at | 创建时间 |

### RECORD_DRAFT

保存 AI 生成的草稿版本。

它存在的原因是：大模型 API 每次调用本身不会自动记住之前的上下文。如果用户说“还是刚刚那个版本好”，后端必须能找到之前的草稿版本，并把相关内容重新加入 prompt。

| 字段 | 说明 |
|---|---|
| id | 主键，草稿 ID |
| session_id | 外键，属于哪次记录会话 |
| version_no | 草稿版本号 |
| draft_json | 草稿结构化内容 |
| preview_text | 用户可读预览文本 |
| status | active、replaced、confirmed |
| created_at | 创建时间 |

### DAILY_RECORD

保存用户确认后的正式记录。

这张表表示记录已经成立，可以进入飞书写入流程，也可以在用户端最近记录中展示。

| 字段 | 说明 |
|---|---|
| id | 主键，正式记录 ID |
| user_id | 外键，属于哪个用户 |
| session_id | 外键，来自哪次记录会话 |
| final_draft_id | 外键，用户最终确认的草稿 |
| record_date | 记录日期 |
| final_text | 最终确认文本 |
| ai_summary | AI 摘要 |
| ai_score | AI 评分 |
| tags_json | 标签 |
| status | success、sync_failed、blocked |
| confirmed_at | 用户确认时间 |
| created_at | 创建时间 |

### RECORD_DISPLAY

保存用户端最近记录页面真正展示的数据。

用户端不直接预览飞书，而是读取本地展示数据。

这张表可以包含管理员评论或每日内容合成后的展示结果。

| 字段 | 说明 |
|---|---|
| id | 主键，展示记录 ID |
| record_id | 外键，对应哪条正式记录 |
| title | 展示标题 |
| summary | 展示摘要 |
| score | 展示评分 |
| display_status | 展示状态 |
| admin_content_json | 管理员附加展示内容 |
| display_json | 最终展示结构 |
| updated_at | 更新时间 |

### DAILY_CONTENT

保存管理员配置的每日内容。

名称使用“每日内容配置”，不叫“每日文案配置”，因为它不局限于文字。

它可以控制：

- 每日提示
- 今日关注点
- 用户端背景图
- 用户端展示卡片
- 记录页默认引导
- 管理员反馈
- 特殊提醒

| 字段 | 说明 |
|---|---|
| id | 主键，每日内容 ID |
| target_user_id | 外键，给哪个用户展示 |
| created_by | 外键，谁创建的，通常是管理员 |
| content_date | 哪一天展示 |
| content_type | text、background、card、reminder、feedback |
| display_area | home、record_page、recent_records |
| content_json | 具体展示内容 |
| resource_id | 外键，关联图片或文件 |
| enabled | 是否启用 |
| created_at | 创建时间 |
| updated_at | 更新时间 |

### RESOURCE_FILE

保存上传文件的元信息。

文件本体不建议直接塞进数据库。更合理的是把文件保存在服务器目录、对象存储或图床中，然后数据库保存文件路径和访问地址。

例如：

```text
/uploads/backgrounds/2026-05-26.jpg
```

| 字段 | 说明 |
|---|---|
| id | 主键，资源 ID |
| uploaded_by | 外键，谁上传的 |
| file_type | image、audio、video、other |
| usage_type | background、record_audio、attachment |
| file_name | 原始文件名 |
| file_url | 文件访问地址 |
| storage_path | 服务器保存路径 |
| mime_type | 文件类型 |
| file_size | 文件大小 |
| created_at | 上传时间 |

### FEISHU_SYNC

保存飞书同步状态。

飞书写入失败时，本地记录不能丢，所以需要保存 payload、失败原因和重试次数。

| 字段 | 说明 |
|---|---|
| id | 主键，同步记录 ID |
| record_id | 外键，对应哪条正式记录 |
| config_id | 外键，使用哪份飞书配置或 Schema |
| target_type | doc 或 bitable |
| target_id | 飞书目标文档或表格 ID |
| payload_json | 实际写入飞书的 payload |
| feishu_ref_id | 飞书返回的记录 ID |
| sync_status | pending、success、failed |
| error_message | 失败原因 |
| retry_count | 重试次数 |
| last_sync_at | 最近同步时间 |
| created_at | 创建时间 |

### APP_CONFIG

保存非敏感系统配置。

适合保存：

- 飞书字段 Schema
- Prompt 模板
- 展示配置
- MCP Payload 规范

不适合保存：

- API Key
- 飞书 Token
- 模型密钥

敏感配置应该放环境变量或外部配置文件。

| 字段 | 说明 |
|---|---|
| id | 主键，配置 ID |
| config_key | 配置名 |
| config_type | feishu_schema、prompt、display、model |
| config_value | 配置内容 |
| enabled | 是否启用 |
| updated_at | 更新时间 |

### USER_BINDING

保存用户之间的绑定关系。

后续如果“对方可以评论、改风格、管理奖品权利”，先查绑定关系和授权，不要直接在业务模块里硬编码。

### USER_PERMISSION

保存绑定关系下的授权项。

例如：

- `comment_record`
- `update_style`
- `manage_reward_grant`

### USER_STYLE

保存用户端背景、主题和风格配置。

这类数据只影响本地展示，不进入飞书同步链路。

### RECORD_COMMENT

保存绑定用户或本人对记录的评论。

评论关联本地 `record_id` 和作者，不写飞书。

V4 起保存绑定用户打分：

| 字段 | 说明 |
|---|---|
| score | 绑定用户给记录的 0-100 分打分 |
| updated_at | 评论或打分最近更新时间 |
| record_id + author_user_id | 每个评论人对每条记录只有一条有效评论，重复保存走更新 |

### POINT_ACCOUNT 与 POINT_LEDGER

保存积分账户和积分流水。

积分余额从流水归集而来，排查积分问题时优先看 `POINT_LEDGER`，不要只看余额。

V4 起积分来源需要可幂等定位：

| 来源 | source_type | source_key |
|---|---|---|
| 每日签到 | `checkin` | `checkin:<userId>:<date>` |
| 绑定用户记录打分 | `record_score` | `record_score:<recordId>` |
| 奖品兑换扣分 | `reward_redeem` | `reward:<rewardId>` |

记录打分积分规则为 `floor((AI 分数 * 50% + 绑定用户打分 * 50%) / 10)`，单条记录最高 10 分；重复改分只按差额调整。

### REWARD_ITEM、REWARD_GRANT、REWARD_REDEMPTION

保存奖品、奖品权利授权和兑换记录。

“把奖品权利交给对方”属于 `points` 主模块，权限校验依赖 `relationship`。

V4 起 `REWARD_ITEM` 保存 `created_by_user_id` 和 `redeemed_at`。用户兑换后：

- `REWARD_ITEM.status` 从 `active` 改为 `redeemed`，可兑换列表不再返回。
- `REWARD_REDEMPTION` 记录兑换事实。
- 绑定管理员视角通过兑换记录看到奖品已被兑换提示。

### OPS_AUDIT_LOG

保存后台人员的高权限操作审计。

后台重试、重写入、测试类操作后续都应记录 operator、action、target 和 payload 摘要。

---

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
| 身份 | APP_PERSON | 保存用户、绑定用户、后台人员等系统使用者 |
| 绑定和授权 | USER_BINDING、USER_PERMISSION | 保存用户之间的绑定关系和授权范围 |
| 记录过程 | RECORD_SESSION | 一次对话式记录过程 |
| 记录过程 | RECORD_MESSAGE | 用户文本、语音识别文本、修改指令、AI 或系统消息 |
| 记录过程 | RECORD_DRAFT | AI 每次生成或修改后的草稿版本 |
| 正式记录 | DAILY_RECORD | 用户确认后的正式记录 |
| 展示数据 | RECORD_DISPLAY | 用户端首页和最近记录真正读取的本地展示数据 |
| 每日内容 | DAILY_CONTENT | 管理员配置的每日提示、主题、引导、卡片、提醒 |
| 风格配置 | USER_STYLE | 用户端背景、主题、风格配置 |
| 评论 | RECORD_COMMENT | 本地记录评论，不写入飞书 |
| 积分 | POINT_ACCOUNT、POINT_LEDGER | 积分账户和流水 |
| 奖品 | REWARD_ITEM、REWARD_GRANT、REWARD_REDEMPTION | 奖品、奖品权利授权和兑换 |
| 资源元信息 | RESOURCE_FILE | 文件元信息；MVP 默认不做真实文件上传 |
| 外部同步 | FEISHU_SYNC | 飞书写入 payload、同步状态、错误原因、重试次数 |
| 非敏感配置 | APP_CONFIG | 飞书 Schema、Prompt、展示配置、MCP Payload 规范 |
| 后台审计 | OPS_AUDIT_LOG | 后台人员测试、重试、重写入等高权限操作审计 |

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

当前 01-优化 MVP 已补：

- APP_PERSON.current_view_role
- USER_BINDING、USER_PERMISSION 双向绑定种子
- POINT_ACCOUNT、POINT_LEDGER 签到、记录打分、兑换流水
- RECORD_COMMENT 评论和绑定用户打分
- REWARD_ITEM 内置奖品、绑定管理员添加奖品
- REWARD_REDEMPTION 兑换记录和绑定用户提示

第二阶段或按需再补：

- APP_CONFIG：当 Prompt、飞书 Schema、展示配置需要后台可维护时再落库；密钥仍然不能入库。
- RESOURCE_FILE：ER 图里已有，但接口 MVP 暂不支持上传背景图、上传照片或长期保存语音音频；没有真实文件能力时不要提前实现复杂存储。
- USER_STYLE、REWARD_GRANT、OPS_AUDIT_LOG：已在 Flyway V3 预留表边界；具体接口按后续 `docs/future` 文档逐步实现。

## 关键关系

- 一个 APP_PERSON 可以有多次 RECORD_SESSION。
- 一次 RECORD_SESSION 可以包含多条 RECORD_MESSAGE。
- 一次 RECORD_SESSION 可以产生多个 RECORD_DRAFT。
- 一次 RECORD_SESSION 最终最多确认成一条 DAILY_RECORD。
- DAILY_RECORD 指向最终确认的 RECORD_DRAFT。
- DAILY_RECORD 必须有本地展示数据 RECORD_DISPLAY，至少要能表达成功、失败或异常状态。
- DAILY_RECORD 可以对应多条 FEISHU_SYNC，用于首次写入和后续重试。
- DAILY_CONTENT 面向某个 target_user 和 content_date 生效。
- USER_BINDING 和 USER_PERMISSION 决定绑定用户能否评论、改风格或管理奖品权利。
- RECORD_COMMENT 只依赖本地 record_id，不进入 FEISHU_SYNC。
- POINT_LEDGER 是积分变更事实来源，POINT_ACCOUNT.balance 只是当前余额。
- OPS_AUDIT_LOG 只记录后台人员高权限操作，不代替业务表状态。

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
