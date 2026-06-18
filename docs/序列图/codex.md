# 序列图 Codex 入口

本目录根据 `docs` 里的 UI、活动图、架构图和数据库设计整理。序列图用于补齐前后端联调时最容易缺失的调用顺序：前端调用哪个业务 API，业务后端读写哪些本地表，什么时候调用 `third` workflow，什么时候触达 AI、ASR 和飞书。

## 推荐阅读顺序

1. [01_用户首页与最近记录序列图.md](01_用户首页与最近记录序列图.md)：用户端只读展示数据的链路。
2. [02_记录草稿生成序列图.md](02_记录草稿生成序列图.md)：记录对话页从输入到 AI 草稿的链路。
3. [03_确认写入与飞书同步序列图.md](03_确认写入与飞书同步序列图.md)：用户确认后，生成 payload、校验、写飞书和本地展示落库的链路。
4. [04_管理员每日内容配置序列图.md](04_管理员每日内容配置序列图.md)：管理员配置每日内容后，用户首页读取配置的链路。
5. [05_管理员异常处理与重试序列图.md](05_管理员异常处理与重试序列图.md)：管理员查看异常、重试飞书同步和修正展示数据的链路。

## 参与方口径

| 参与方 | 说明 |
|---|---|
| 用户端前端 | `docs/ui` 里的手机端页面：首页、记录对话页、最近记录页。 |
| 管理员端前端 | `docs/ui` 里的 PC 后台：首页、每日内容配置页、用户最近记录页、记录详情页。 |
| SpringBoot API | 面向前端的业务 API 层，负责鉴权、幂等、本地业务表读写和调用 `third`。 |
| MySQL 业务库 | 保存 `APP_PERSON`、`RECORD_SESSION`、`RECORD_MESSAGE`、`RECORD_DRAFT`、`DAILY_RECORD`、`RECORD_DISPLAY`、`DAILY_CONTENT`、`FEISHU_SYNC` 等业务表。 |
| third Workflow API | Python `third` 服务，提供 `/workflows/invoke`、`/workflows/{session_id}`、`/workflows/{session_id}/resume`。 |
| third worker | 消费 Redis 队列，执行 workflow plan、Agent、校验节点和 Tool。 |
| MySQL third 库或 third_* 表 | 保存 workflow session、plan、step、artifact、prompt、tool registry。 |
| Redis | 保存 workflow 队列、锁、游标、短期 artifact 和幂等 key。 |
| OpenAI API | workflowagent 和业务 Agent 的模型调用。 |
| ASR 服务 | 语音识别服务，MVP 只保存识别后的 `asrText`。 |
| 飞书 OpenAPI | 通过 `third` Tool 写入飞书多维表格或文档。 |

## 设计边界

- 前端只调用 SpringBoot `/api` 接口，不直接调用 `third`、OpenAI、ASR 或飞书。
- 用户端首页和最近记录只读本地 `RECORD_DISPLAY`、`DAILY_RECORD` 与 `DAILY_CONTENT`，不直接读飞书。
- 每次用户输入、语音识别结果和修改指令都要落 `RECORD_MESSAGE`。
- 每次 AI 生成或修改草稿都要新增 `RECORD_DRAFT` 版本，不能只覆盖旧草稿。
- 用户确认写入时必须使用 `clientConfirmId` 做幂等，重复确认不能重复创建 `DAILY_RECORD`，也不能重复写飞书。
- 飞书失败不能丢本地记录，需要保存 payload 快照、失败原因、可重试状态和用户端展示状态。

## 相关文档

- 前后端接口契约：[../接口文档.md](../接口文档.md)
- UI 页面说明：[../ui/codex.md](../ui/codex.md)
- UI 页面流程：[../ui/页面流程图.md](../ui/页面流程图.md)
- 数据库入口：[../数据库/codex.md](../数据库/codex.md)
- 总架构图：[../架构图/01_总架构图.md](../架构图/01_总架构图.md)
- 记录闭环活动图：[../活动图/整体新增记录闭环活动图_优化版.md](../活动图/整体新增记录闭环活动图_优化版.md)
