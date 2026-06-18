# backend Codex 入口

本目录是 SpringBoot 业务后端。Codex 实现或排查后端时先读这里，再看 `docs/接口文档.md`。

## 模块划分

| 模块 | 位置 | 作用 |
|---|---|---|
| common | `src/main/java/com/formygirl/common` | 统一响应、异常、requestId、CORS、配置和 JSON 工具。 |
| auth | `src/main/java/com/formygirl/auth` | MVP 固定账号登录，Bearer token 到 USER/ADMIN 的映射。 |
| record | `src/main/java/com/formygirl/record` | 用户首页、记录会话、消息、草稿、确认写入、最近记录和业务 SQL。 |
| admin | `src/main/java/com/formygirl/admin` | 管理员首页、每日内容、记录列表、详情、重试和展示修正。 |
| trace | `src/main/java/com/formygirl/trace` | 聚合 session、message、draft、record、display、sync 和 third workflow 追踪信息。 |
| thirdclient | `src/main/java/com/formygirl/thirdclient` | 封装 third workflow 的提交、查询、resume、artifact 和 timeline。 |
| migration | `src/main/resources/db/migration` | Flyway 业务表和初始化数据，目标逻辑库是 `for_mygirl_app`。 |

## 实现口径

- 前端只调用 `/api`，不直接调用 third。
- 后端业务表使用 `for_mygirl_app`，third workflow 表使用 `third_service`，两者只通过 `third_session_id` 和 HTTP 调用关联。
- 用户端展示以 `RECORD_DISPLAY` 为准，不直接读取飞书。
- 记录消息幂等依赖 `client_message_id`，确认写入幂等依赖 `client_confirm_id`。
- `third_session_id` 要保存到消息、草稿、正式记录或同步记录里，方便 `record-traces` 反查。
- 确认写入失败时也要保留 `DAILY_RECORD`、`FEISHU_SYNC.payload_json` 和 `RECORD_DISPLAY`。
- 新增 Controller、Service、Client、API helper 函数前保留简短中文注释。

## 相关文档

- 接口契约：`../docs/接口文档.md`
- 序列图：`../docs/序列图/codex.md`
- 数据库说明：`../docs/数据库/codex.md`
- third 服务：`../third/codex.md`
