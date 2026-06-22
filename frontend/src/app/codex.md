# app 层入口

`src/app` 放前端应用级编排，不放具体业务 API。它可以组合多个 feature，但不能绕过 feature `api.ts` 直接请求后端。

## 当前文件

- `LoginScreen.tsx`：登录表单、本地验证码校验和提交事件。
- `MobileWorkspace.tsx`：手机端用户视角和绑定管理员视角的页面状态编排。

## 接入规则

1. `src/App.tsx` 只负责登录分流：普通账号进入 `MobileWorkspace`，后台账号进入 `features/ops`。
2. 手机端如果需要跨 `record`、`relationship`、`comment`、`points` 组合数据，放在 `MobileWorkspace.tsx`。
3. 新接口先放回对应 feature 的 `api.ts`，不要在 app 层直接写 `apiRequest`。
4. 页面级异步动作统一设置 loading/status，避免静默失败。
