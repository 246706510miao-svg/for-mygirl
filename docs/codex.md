# docs Codex 总入口

本文件是 `docs` 目录的总入口。Codex 读完这里后，应能快速判断：当前任务要看哪些文档、哪些规则是权威约束、哪些旧图只做参考。

## 项目一句话

这是一个个人使用的日常记录 Web 应用。用户在 iPhone Web/PWA 上通过文本或语音做日常记录，AI 帮助生成草稿、摘要、标签和评分；用户确认后，后端校验 AI 生成的飞书 MCP Payload，再写入飞书，同时把本地记录、展示数据、同步状态和异常原因保存到数据库。管理员在 PC Web 后台配置每日内容、查看记录状态并处理同步异常。

## 先看哪份文档

| 你要做什么 | 先看 | 再看 |
|---|---|---|
| 判断系统边界、模块归属、部署结构 | [架构图/codex.md](./架构图/codex.md) | [架构图/01_总架构图.mermaid](./架构图/01_总架构图.mermaid)、[架构图/04_部署边界图.mermaid](./架构图/04_部署边界图.mermaid) |
| 设计表、写迁移、处理状态流转 | [数据库/codex.md](./数据库/codex.md) | [数据库/数据库说明.md](./数据库/数据库说明.md)、[数据库/ER图.mermaid](./数据库/ER图.mermaid) |
| 实现后端接口、前端 API Client 或接口测试 | [接口定义/codex.md](./接口定义/codex.md) | [接口定义/接口定义说明.md](./接口定义/接口定义说明.md) |
| 理解某个业务调用顺序 | [序列图/codex_序列图实现约束.md](./序列图/codex_序列图实现约束.md) | `序列图/01` 到 `07` 中对应链路 |
| 理解新增记录、AI Payload、管理员操作、状态流转 | [活动图/记录状态流转图_优化版.mermaid](./活动图/记录状态流转图_优化版.mermaid) | [活动图/整体新增记录闭环活动图_优化版.mermaid](./活动图/整体新增记录闭环活动图_优化版.mermaid) |

## 权威规则

如果不同文档之间有轻微差异，按以下规则收敛：

- 模块名统一使用“每日内容配置”，不要写成“每日文案配置”。
- 飞书同步失败状态统一使用 `sync_failed`，不要使用 `feishu_failed`。
- `RECORD_SESSION.status` 可使用 `editing`、`previewing`、`confirming`、`confirmed`、`cancelled`。
- `DAILY_RECORD.status` 使用 `success`、`sync_failed`、`blocked`。
- `FEISHU_SYNC.sync_status` 使用 `pending`、`success`、`failed`。
- 用户端首页和最近记录只读本地 `DAILY_CONTENT`、`RECORD_DISPLAY`、`DAILY_RECORD`，不直接读飞书。
- AI 生成的飞书 MCP Payload 必须由后端校验后才能执行。
- 密钥、Token、模型配置等敏感信息只能放外部配置文件或环境变量，不能放前端或提交到代码仓库。

## MVP 边界

### 必须覆盖

- 用户文本记录生成 AI 草稿。
- 用户语音记录经 ASR 后生成 AI 草稿。
- 用户继续用自然语言修改草稿。
- 用户确认写入，后端幂等处理并同步飞书。
- 飞书失败时本地保留正式记录、payload、错误原因和展示状态。
- 用户首页展示每日内容和最近记录。
- 管理员配置每日内容。
- 管理员查看异常并重试飞书同步。

### 暂时不做

- 原生 iOS App、小程序。
- 复杂多用户系统、复杂权限系统。
- 上传背景图、上传照片、服务器文件存储、对象存储、图床。
- 长期保存语音音频。
- 管理员统计图表。
- 飞书内容直接预览。
- 多服务器部署、微服务拆分、复杂消息队列。

## 核心闭环

```text
文本/语音输入
  -> 后端保存 RECORD_MESSAGE
  -> AI 生成 RECORD_DRAFT
  -> 用户继续修改或确认
  -> 后端用 clientConfirmId 做幂等
  -> 创建 DAILY_RECORD
  -> AI 生成飞书 MCP Payload
  -> 后端校验 Payload
  -> 调用飞书 MCP
  -> 保存 FEISHU_SYNC
  -> 生成/更新 RECORD_DISPLAY
  -> 用户端最近记录展示本地状态
```

## 模块速查

| 模块 | 关键文件 | 你能从这里获得什么 |
|---|---|---|
| 架构图 | [架构图/codex.md](./架构图/codex.md) | 前后端边界、后端模块、部署边界、MVP 禁止事项 |
| 数据库 | [数据库/codex.md](./数据库/codex.md) | 表分组、关系、状态、不变量、API 到表的映射 |
| 接口定义 | [接口定义/codex.md](./接口定义/codex.md) | API 清单、关键请求响应、幂等、chatReply、displayRecord |
| 序列图 | [序列图/codex_序列图实现约束.md](./序列图/codex_序列图实现约束.md) | 文本、语音、修改、确认、首页、每日内容、异常重试的调用顺序 |
| 活动图 | [活动图/整体新增记录闭环活动图_优化版.mermaid](./活动图/整体新增记录闭环活动图_优化版.mermaid) | 业务活动、状态流转和异常路径 |

## 按任务找文档

### 做用户端记录页

1. [接口定义/codex.md](./接口定义/codex.md)
2. [序列图/01_用户文本记录生成草稿序列图.mermaid](./序列图/01_用户文本记录生成草稿序列图.mermaid)
3. [序列图/02_用户语音记录生成草稿序列图.mermaid](./序列图/02_用户语音记录生成草稿序列图.mermaid)
4. [序列图/03_用户继续修改草稿序列图.mermaid](./序列图/03_用户继续修改草稿序列图.mermaid)
5. [序列图/04_用户确认写入飞书序列图.mermaid](./序列图/04_用户确认写入飞书序列图.mermaid)

### 做用户端首页

1. [接口定义/codex.md](./接口定义/codex.md)
2. [序列图/06_用户端加载首页序列图.mermaid](./序列图/06_用户端加载首页序列图.mermaid)
3. [数据库/codex.md](./数据库/codex.md) 中 `DAILY_CONTENT`、`RECORD_DISPLAY`、`DAILY_RECORD`

### 做管理员后台

1. [接口定义/codex.md](./接口定义/codex.md)
2. [序列图/05_管理员配置每日内容序列图.mermaid](./序列图/05_管理员配置每日内容序列图.mermaid)
3. [序列图/07_管理员查看和处理异常序列图.mermaid](./序列图/07_管理员查看和处理异常序列图.mermaid)
4. [活动图/管理员相关活动图_优化版.mermaid](./活动图/管理员相关活动图_优化版.mermaid)

### 做后端确认写入和飞书同步

1. [架构图/codex.md](./架构图/codex.md)
2. [接口定义/codex.md](./接口定义/codex.md) 中 confirm 和 retry-sync
3. [数据库/codex.md](./数据库/codex.md) 中 DAILY_RECORD、FEISHU_SYNC、RECORD_DISPLAY
4. [序列图/04_用户确认写入飞书序列图.mermaid](./序列图/04_用户确认写入飞书序列图.mermaid)

### 做数据库迁移

1. [数据库/codex.md](./数据库/codex.md)
2. [数据库/ER图.mermaid](./数据库/ER图.mermaid)
3. [数据库/数据库说明.md](./数据库/数据库说明.md)

### 做部署或环境配置

1. [架构图/codex.md](./架构图/codex.md)
2. [架构图/04_部署边界图.mermaid](./架构图/04_部署边界图.mermaid)
3. [架构图/05_部署访问流程图.mermaid](./架构图/05_部署访问流程图.mermaid)

## Codex 执行原则

- 优先完成 MVP 闭环，不主动扩大范围。
- 前端只做展示、输入、录音、调用后端和状态呈现。
- 后端是所有 AI、ASR、飞书 MCP 调用的唯一入口。
- 所有可变目标、Prompt、Schema 和密钥都要从配置读取；密钥不入库。
- 所有 AI 输出进入外部系统前都要校验。
- confirm 和 retry-sync 都要有次数上限，不能无限重试。
- 新增字段、接口或模块时，先检查本入口对应的模块文档，避免和现有命名、状态、闭环冲突。
