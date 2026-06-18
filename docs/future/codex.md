# future 文档入口

`docs/future` 用来描述后续要增加或重构的功能。它比旧活动图和 UI 原型优先级更高；后续新增内容先写这里，再改代码。

## 使用方式

1. 复制 [模板.md](模板.md) 为 `<功能名>.md`。
2. 按模块写清楚功能归属，不按页面随意拆。
3. 文档确认后再改 `backend/`、`frontend/`、数据库 migration 和接口文档。
4. 改完后更新相关 `codex.md`，保证下一次能从文档找到代码入口。

## 当前计划

| 文档 | 用途 |
|---|---|
| [01-优化mvp功能.md](01-优化mvp功能.md) | 按当前手机端双向绑定 UI 收敛 MVP 范围；已落地两个普通用户 + 独立 OPS、绑定视角、签到/打分积分、奖品、兑换记录和评论打分。 |

## 模块归属速查

| 功能类型 | 主模块 | 协作模块 |
|---|---|---|
| 写记录、改草稿、确认写入 | `record` | `sync`、`thirdclient`、`trace` |
| 用户绑定、授权对方能力 | `relationship` | `identity` |
| 改背景、主题、用户端风格 | `style` | `relationship` |
| 对记录评论 | `comment` | `relationship`、`record/display` |
| 积分账户、流水 | `points` | `comment`、`record/display` |
| 奖品、兑换、奖品权利交给对方 | `points` | `relationship` |
| 飞书同步、重试、重写入 | `sync` | `ops`、`thirdclient`、`trace` |
| 全量查看、测试、后台操作 | `ops` | `trace`、`sync` |

## 检查项

- 是否明确谁可以使用：`USER`、绑定用户、`OPS_ADMIN`。
- 是否明确主模块和协作模块。
- 是否说明前端文件位置和后端包位置。
- 是否说明新增或变更的表。
- 是否说明接口路径、请求、响应和错误。
- 是否说明是否进入飞书；评论、风格和积分默认不进入飞书。
- 是否说明排查入口和关键 ID。
