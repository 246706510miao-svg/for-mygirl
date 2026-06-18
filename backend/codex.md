# backend Codex 入口

本目录是 SpringBoot 业务后端。后续开发按模块找入口，不再把“用户互动能力”和“后台运维能力”都塞进 `admin`。

## 先读什么

1. 新增功能先读对应 `docs/future/*.md`。
2. 对接口不确定时读 `../docs/接口文档.md`。
3. 对表和状态不确定时读 `../docs/数据库/codex.md` 和 Flyway migration。
4. 对记录链路排查时读本文件的“链路定位”。

## 模块划分

| 模块 | 位置 | 作用 |
|---|---|---|
| common | `src/main/java/com/formygirl/common` | 统一响应、异常、requestId、CORS、配置、JSON 和 ID 工具。 |
| identity | `src/main/java/com/formygirl/identity` | 登录、当前用户解析、`USER` / `OPS_ADMIN` 角色口径，以及 `USER` / `BOUND_ADMIN` 手机端视角。 |
| user | `src/main/java/com/formygirl/user` | 登录用户首页、最近记录和后续用户端总览接口。 |
| relationship | `src/main/java/com/formygirl/relationship` | 用户绑定、绑定状态、授权范围。对方能否评论、改风格、管理奖品先查这里。 |
| record | `src/main/java/com/formygirl/record` | 记录主链路：会话、消息、草稿、确认、正式记录和展示。 |
| record/session | `src/main/java/com/formygirl/record/session` | `/api/record-sessions/*` 控制器入口。 |
| style | `src/main/java/com/formygirl/style` | 用户端背景、主题、风格配置；不进入飞书同步。 |
| comment | `src/main/java/com/formygirl/comment` | 绑定用户对记录的评论和打分；只落本地业务库，不写飞书，并触发记录打分积分。 |
| points | `src/main/java/com/formygirl/points` | 签到积分、记录打分积分、积分流水、奖品、兑换和兑换提示。 |
| sync | `src/main/java/com/formygirl/sync` | 飞书 payload、同步状态、失败保留、重试和重写入。 |
| trace | `src/main/java/com/formygirl/trace` | 只读聚合 session、message、draft、record、display、sync 和 third workflow。 |
| ops | `src/main/java/com/formygirl/ops` | 后台人员模块：全量记录、测试、追踪、重试、重写入。当前接口路径仍兼容 `/api/admin/*`。 |
| thirdclient | `src/main/java/com/formygirl/thirdclient` | SpringBoot 调用 Python `third` workflow 的 HTTP 适配。 |
| persistence | `src/main/java/com/formygirl/persistence` | 业务库 SQL。当前 `BusinessRepository` 是过渡聚合仓储，新增功能优先拆独立 Repository。 |
| migration | `src/main/resources/db/migration` | Flyway 业务表。`V3__future_module_tables.sql` 预留模块表，`V4__mvp_binding_points_comments.sql` 落地双用户绑定、积分奖品、评论打分和兑换记录。 |

## 当前 MVP 接口入口

| 能力 | 入口 |
|---|---|
| 登录和当前视角 | `identity/IdentityController.java`、`identity/IdentityViewController.java` |
| 绑定关系 | `relationship/RelationshipController.java` |
| 当前用户最近记录 | `user/UserController.java` 的 `/api/records/recent` |
| 绑定用户最近记录 | `user/UserController.java` 的 `/api/bound-user/records/recent` |
| 评论和打分 | `comment/CommentController.java` |
| 签到、积分、奖品、兑换 | `points/PointController.java` |
| 记录对话和确认 | `record/session/RecordSessionController.java` |
| 独立后台运维 | `ops/OpsController.java`，仍兼容 `/api/admin/*` |

## 链路定位

| 问题 | 先看 | 再看 |
|---|---|---|
| 登录、角色、token | `identity` | `common/AppProperties.java` |
| 手机端视角不对 | `identity` | `relationship`、`APP_PERSON.current_view_role` |
| 用户首页或最近记录 | `user` | `record`、`persistence` |
| 写记录、生成草稿、确认 | `record/session` | `record`、`thirdclient`、`persistence` |
| 飞书失败、重试、重写入 | `sync` | `ops`、`thirdclient`、`trace` |
| 记录链路排查 | `trace` | `record`、`sync`、third workflow 表 |
| 绑定用户和权限 | `relationship` | `identity` |
| 背景或风格异常 | `style` | `relationship` |
| 对方评论或打分异常 | `comment` | `relationship`、`record/display` |
| 签到、积分或奖品异常 | `points` | `relationship`、`POINT_LEDGER` |
| 奖品兑换后仍显示 | `points` | `REWARD_ITEM.status`、`REWARD_REDEMPTION` |
| 后台人员测试能力 | `ops` | `trace`、`sync` |

## 新增功能流程

1. 先按 `../docs/future/模板.md` 写功能文档，明确接入模块、权限、接口、数据库、外部服务和排查入口。
2. 后端只在对应模块新增 Controller、Service、Repository，不要扩张无关模块。
3. 涉及数据库时新增 Flyway migration；不要直接改已上线 migration。
4. 涉及前端时同步更新 `../frontend/codex.md` 对应 feature。
5. 涉及记录、同步、积分等跨链路行为时，补充 trace 或审计字段，确保能按 ID 反查。

## 实现口径

- 前端只调用 SpringBoot `/api`，不直接调用 `third`。
- 用户端展示以 `RECORD_DISPLAY` 和后续本地展示表为准，不直接读取飞书。
- 评论、风格、积分和奖品是本地用户产品能力，默认不写飞书。
- 后台人员能力放 `ops`，不要再把伴侣/绑定用户能力放进后台模块。
- 手机端管理员视角必须通过 `relationship` 校验绑定对象，不能调用 `/api/admin/*`。
- 记录打分积分由 `comment` 触发、`points` 落流水，使用 `record_score:<recordId>` 幂等键。
- 奖品兑换后 `REWARD_ITEM.status=redeemed`，兑换提示从 `REWARD_REDEMPTION` 查。
- `third_session_id` 要保存到消息、草稿、正式记录或同步记录里，方便 `trace` 反查。
- 新增 Controller、Service、Client、API helper 函数前保留简短中文注释。

## 相关文档

- 后续功能模板：`../docs/future/codex.md`
- 接口契约：`../docs/接口文档.md`
- 数据库说明：`../docs/数据库/codex.md`
- 前端入口：`../frontend/codex.md`
- third 服务：`../third/codex.md`
