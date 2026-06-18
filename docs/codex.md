# docs 目录 Codex 入口

本文件是 `docs` 目录的总入口。后续新增内容优先按 `future` 文档模板描述模块、权限、接口、数据库和排查入口；旧的活动图和 UI 原型只作为历史参考，不再作为新增功能的主要来源。

## 推荐阅读顺序

1. 新增功能或改功能，先读 [future/codex.md](future/codex.md)，再按 [future/模板.md](future/模板.md) 写功能文档。
2. 实现后端时读 [../backend/codex.md](../backend/codex.md)，确认功能应该落在哪个模块。
3. 实现前端时读 [../frontend/codex.md](../frontend/codex.md)，确认 feature、API helper 和 DTO 位置。
4. 涉及接口契约时读 [接口文档.md](接口文档.md)。
5. 涉及表、状态、幂等和追踪 ID 时读 [数据库/codex.md](数据库/codex.md)。
6. 本地启动、Docker 重建、volume 保留和接口没刷新时读 [运行与刷新.md](运行与刷新.md)。
7. 排查旧记录闭环时再读 [序列图/codex.md](序列图/codex.md)、[架构图/01_总架构图.md](架构图/01_总架构图.md) 和活动图。

## 当前架构口径

系统按模块而不是页面拆分：

| 领域 | 后端模块 | 前端 feature | 数据边界 |
|---|---|---|---|
| 身份和视角 | `identity` | `src/App.tsx`、`features/relationship` | `APP_PERSON.current_view_role` |
| 用户首页和记录展示 | `user`、`record/display` | `features/record` | `DAILY_RECORD`、`RECORD_DISPLAY` |
| 记录写入主链路 | `record/session`、`record` | `features/record` | `RECORD_SESSION`、`RECORD_MESSAGE`、`RECORD_DRAFT` |
| 飞书同步 | `sync`、`thirdclient` | `features/ops` 触发后台动作 | `FEISHU_SYNC` |
| 链路排查 | `trace` | `features/ops` | 业务表 + third workflow 表 |
| 用户绑定 | `relationship` | `features/relationship` | `USER_BINDING`、`USER_PERMISSION` |
| 背景风格 | `style` | `features/style` | `USER_STYLE` |
| 记录评论和打分 | `comment` | `features/comment` | `RECORD_COMMENT` |
| 积分、奖品和兑换 | `points` | `features/points` | `POINT_ACCOUNT`、`POINT_LEDGER`、`REWARD_*` |
| 后台人员 | `ops` | `features/ops` | `OPS_AUDIT_LOG` 和被操作业务表 |

## 后续新增功能方式

新增功能不要先改 UI 原型或活动图，按下面顺序做：

1. 复制 [future/模板.md](future/模板.md) 为 `future/<功能名>.md`。
2. 在文档里写清楚接入模块、用户权限、前端位置、后端位置、数据库、接口、外部服务、排查入口。
3. 如果功能跨模块，写清楚主模块和协作模块。例如“奖品权利交给对方”：主模块是 `points`，授权协作模块是 `relationship`。
4. 再改 `backend/`、`frontend/` 和 Flyway migration。
5. 最后更新对应 `codex.md`，让下一次 Codex 能直接知道从哪里进入。

## 目录

### future

| 文档 | 用途 |
|---|---|
| [future/codex.md](future/codex.md) | 后续功能文档入口，说明模板使用方式、模块归属和落地检查项。 |
| [future/模板.md](future/模板.md) | 新功能文档模板。 |
| [future/01-优化mvp功能.md](future/01-优化mvp功能.md) | 当前手机端双向绑定 MVP，实现两个普通用户、绑定管理员视角、积分奖品、评论打分和兑换记录。 |

### 实现工程

| 文档 | 用途 |
|---|---|
| [运行与刷新.md](运行与刷新.md) | 本地 Docker 启动、前后端重建、migration 执行、MySQL/Redis volume 保留和常见刷新问题。 |
| [../backend/codex.md](../backend/codex.md) | SpringBoot 后端模块入口，说明 identity、record、relationship、style、comment、points、sync、trace、ops 等边界。 |
| [../frontend/codex.md](../frontend/codex.md) | React 前端 feature 入口，说明 record、style、relationship、comment、points、ops 等边界。 |

### 接口和数据

| 文档 | 用途 |
|---|---|
| [接口文档.md](接口文档.md) | 当前前后端 API 设计，包含统一响应、鉴权、幂等字段、记录追踪、用户端接口、记录会话接口和后台接口。 |
| [数据库/codex.md](数据库/codex.md) | 数据库模块主入口，说明核心表、状态值、数据不变量和 API 到表的对应关系。 |
| [数据库/ER图.md](数据库/ER图.md) | Mermaid ER 图。后续新增表后需要同步更新。 |

### 旧流程资料

这些资料仍可用于理解现有 MVP，但新增功能不优先从这里设计：

| 文档 | 用途 |
|---|---|
| [ui/codex.md](ui/codex.md) | 静态 UI 原型说明。 |
| [ui/页面流程图.md](ui/页面流程图.md) | 旧页面级流程。 |
| [序列图/codex.md](序列图/codex.md) | 旧序列图目录入口。 |
| [架构图/01_总架构图.md](架构图/01_总架构图.md) | 旧总体架构图。 |
| [架构图/02_部署边界图.md](架构图/02_部署边界图.md) | 部署边界。 |
| [活动图/整体新增记录闭环活动图_优化版.md](活动图/整体新增记录闭环活动图_优化版.md) | 旧记录闭环活动图。 |
| [活动图/管理员相关活动图_优化版.md](活动图/管理员相关活动图_优化版.md) | 旧管理员流程，后续应拆成 `relationship/style/comment/points/ops`。 |

## 排查提示

- 用户写记录出问题：`features/record` -> `backend record/session` -> `record` -> `thirdclient` / `sync`。
- 对方权限出问题：`features/relationship` -> `backend relationship` -> `USER_BINDING` / `USER_PERMISSION`。
- 评论没显示：`features/comment` -> `backend comment` -> `RECORD_COMMENT`，不要查飞书。
- 背景风格异常：`features/style` -> `backend style` -> `USER_STYLE`。
- 积分、奖品或兑换异常：`features/points` -> `backend points` -> `POINT_LEDGER` / `REWARD_*`。
- 后台重试或重写入异常：`features/ops` -> `backend ops` -> `trace` -> `sync` -> `thirdclient`。
- 新接口返回 `No static resource ...`：优先读 [运行与刷新.md](运行与刷新.md)，确认 Docker 后端镜像是否重新 build、Flyway 是否跑到当前版本。
