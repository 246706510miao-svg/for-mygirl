# frontend Codex 入口

本目录是 Vite React TypeScript 前端。后续开发按 feature 模块进入

## 先读什么

1. 新增功能先读对应 `../docs/future/*.md`。
2. 找接口路径和 DTO 时读 `../docs/接口文档.md` 和 `src/shared/types/api.ts`。
3. 找模块入口时读本文件的“模块划分”。
4. 修改请求逻辑时先看 `src/shared/api/client.ts`，不要在页面里直接写底层 fetch。

## 模块划分

| 模块                  | 位置                          | 作用                                                               |
| --------------------- | ----------------------------- | ------------------------------------------------------------------ |
| app                   | `src/App.tsx`、`src/app`    | 登录分流和跨 feature 的手机端页面编排；普通用户进入手机端双视角，`OPS_ADMIN` 进入独立后台。 |
| shared/api            | `src/shared/api`            | 统一 API client、token、`X-Request-Id` 和错误处理。              |
| shared/types          | `src/shared/types`          | 根据接口文档维护 DTO 类型。                                        |
| features/record       | `src/features/record`       | 记录写入主链路和最近记录 API：首页、输入、草稿、确认、本人/绑定用户最近记录。 |
| features/newsfocus    | `src/features/newsfocus`    | 首页「今日热门」单卡片与 BottomSheet；按 AI/中国大事/新闻/开源连续分段展示，并提供今日/昨日切换，原文由新窗口外链打开。 |
| features/style        | `src/features/style`        | 背景、主题、用户端风格配置。                                       |
| features/relationship | `src/features/relationship` | 当前登录人、视角切换、用户绑定和授权范围。                         |
| features/comment      | `src/features/comment`      | 绑定管理员对记录评论和打分，只走本地业务库，不进飞书。             |
| features/points       | `src/features/points`       | 签到积分、记录打分积分、奖品、兑换和兑换记录。                     |
| features/ops          | `src/features/ops`          | 后台人员页面：全量记录、详情、追踪、重试、后续重写入。             |
| styles                | `src/styles.css`            | 当前基础样式。后续组件复杂后再拆模块样式。                         |

## 链路定位

| 问题                       | 先看                         | 再看                                                             |
| -------------------------- | ---------------------------- | ---------------------------------------------------------------- |
| 请求失败、token、requestId | `src/shared/api/client.ts` | 浏览器 Network、后端 `common`                                  |
| 登录后页面分流错误         | `src/App.tsx`             | `src/app/LoginScreen.tsx`、后端 `identity`                  |
| 用户/管理员视角错误        | `features/relationship/api.ts` | 后端 `relationship`、`APP_PERSON.current_view_role`       |
| 记录输入或确认异常         | `features/record/api.ts`   | `src/app/MobileWorkspace.tsx`、后端 `record/session`       |
| 背景风格异常               | `features/style`           | 后端 `style`、`relationship`                                 |
| 用户绑定或授权异常         | `features/relationship`    | 后端 `relationship`                                            |
| 评论或打分异常             | `features/comment/api.ts`  | 后端 `comment`、`points`                                      |
| 签到、积分、奖品或兑换异常 | `features/points/api.ts`   | 后端 `points`、`relationship`                                 |
| 后台记录、追踪、重试异常   | `features/ops/api.ts`      | 后端 `ops`、`trace`、`sync`                                |
| 今日热门卡片或抽屉异常     | `features/newsfocus/DailyFocusCard.tsx` | `shared/types/api.ts`、`GET /api/user/home` |

## 新增功能流程

1. 先写 `../docs/future/<功能名>.md`，明确 feature 归属。
2. 前端在 `src/features/<module>` 下新增 `api.ts`、页面组件和必要的 `codex.md` 更新。
3. DTO 放 `src/shared/types/api.ts`，通用请求能力才放 `shared/api`。
4. 页面组件只做状态编排和渲染，接口调用放本 feature 的 `api.ts`。
5. 如果功能需要跨模块，比如“奖品权利交给对方”，由 `relationship` 做授权判断，`points` 做奖品业务，不要互相写内部状态。

## 实现口径

- 当前手机端按 `docs/ui` 页面实现：登录、首页、用户/角色、对话、本人最近记录、绑定管理员积分奖品、绑定管理员最近记录。
- 普通用户登录后默认进入手机端首页，可切换 `USER` / `BOUND_ADMIN`；`admin` 登录进入 `features/ops`。
- `src/App.tsx` 只做登录分流；跨 `record`、`relationship`、`comment`、`points` 的手机端状态编排放 `src/app/MobileWorkspace.tsx`。
- 后台人员页面统一叫 `ops`，即使当前接口路径仍是 `/api/admin/*`。
- 用户端优先适配 iPhone 宽度，按钮最小高度保持 44px。
- API 调用必须经过 `shared/api/client.ts` 和 feature `api.ts`。
- 每日热门不在前端调用第三方来源或抓取文章正文；首页消费 `UserHome.newsFocus`，昨日切换经 feature API 调用 `/api/user/news-focus`，原文链接固定用新窗口打开且不显示数值评分。
- 语音按钮当前是 UI 入口，不接真实 ASR；验证码只做本地开发校验，不调用后端服务。
- 新增 hook、API helper 和页面级函数前保留简短中文注释。

## 相关文档

- 后续功能模板：`../docs/future/codex.md`
- 接口文档：`../docs/接口文档.md`
- 后端入口：`../backend/codex.md`
- 当前 UI 原型：`../docs/ui/codex.md`
- 界面组件与优化说明：`界面组件与优化说明.md`
