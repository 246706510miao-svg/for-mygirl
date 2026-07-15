# UI 页面说明

`index.html` 是当前项目 UI 的可交互原型；视觉以低饱和暖色、内容卡片和清晰的信息层级为主，并保留原项目的毛玻璃质感。页面结构以现有 React 前端和 Spring Boot 接口为准，不使用模板中的演示业务替代真实能力。

## 移动端

| 页面 | 页面内容 | 对应接口 |
| --- | --- | --- |
| 登录 / 注册 | 登录、注册、本地验证码、会话恢复 | `POST /api/auth/login`、`POST /api/auth/register`、`GET /api/auth/me`、`POST /api/auth/logout` |
| 首页 | 问候、签到、独立积分卡、每日热门、记录入口、最近记录 | `GET /api/user/home`、`GET /api/user/news-focus`、`POST /api/points/checkins`、`GET /api/points/summary` |
| 记录对话 | 飞书表选择与设置、文本对话、草稿、third 确认、取消会话 | `/api/user/feishu/**`、`/api/record-sessions/**` |
| 最近记录 | 字段筛选、记录列表、记录详情、对方评论 | `GET /api/records/recent` |
| 我的小世界 | 身份、积分入口、最近奖品预览、双向绑定、邀请处理、照顾者模式入口 | `GET /api/points/summary`、`GET /api/rewards`、`/api/relationship/**`、`POST /api/identity/view-role` |
| 心意商店 | 我的积分、可兑换奖品、兑换记录 | `GET /api/rewards`、`POST /api/rewards/{rewardId}/redeem`、`GET /api/reward-redemptions` |
| 照顾者模式 | 评论 TA 的记录、添加管理奖品；进入和退出时切换绑定管理员视角 | `POST /api/identity/view-role`、`GET /api/bound-user/records/recent`、`POST /api/records/{recordId}/comment`、`POST /api/rewards` |

底部导航固定为“记录 / 日常 / 首页 / 心意 / 我的”，首页位于正中间但不固定放大，只突出当前选中的页面。照顾者模式不占用主导航，也不包含运维后台能力。

## 运维端

| 页面 | 页面内容 | 对应接口 |
| --- | --- | --- |
| 记录与异常 | 今日统计、记录筛选、详情、展示修正、飞书同步重试 | `/api/admin/dashboard`、`/api/admin/records/**` |
| 每日内容 | 按用户和日期读取、编辑、保存首页内容 | `GET/PUT /api/admin/daily-contents` |
| 链路追踪 | 按 Session、Record、Third Session 查询链路 | `/api/admin/record-traces`、`/api/admin/record-sessions/{sessionId}/trace`、`/api/admin/records/{recordId}/trace` |

页面之间的跳转关系见 [页面流程图.md](./页面流程图.md)。
