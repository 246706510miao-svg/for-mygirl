# frontend 初始化说明

`frontend` 是 Vite React TypeScript 前端。当前以接口联调为主，`src/App.tsx` 只负责登录分流，手机端状态编排放在 `src/app/MobileWorkspace.tsx`，业务请求继续按 `features/record`、`features/style`、`features/relationship`、`features/comment`、`features/points`、`features/ops` 维护。

## 本地运行

```powershell
cd frontend
npm install
npm run dev
```

默认地址：

```text
http://localhost:5173
```

本地 `npm run dev` 未设置 `VITE_API_BASE_URL` 时，前端使用相对 `/api`，由 `vite.config.ts` 代理到：

```text
http://localhost:8080
```

Docker 静态包未设置 `VITE_API_BASE_URL` 时，会按当前页面主机推导后端 `:8080`，例如 `http://localhost:5173` 会请求 `http://localhost:8080`。如需固定后端地址：

```powershell
$env:VITE_API_BASE_URL = "http://localhost:8080"
npm run dev
```

## 构建

```powershell
npm run build
```

## 当前页面

- 登录端：开发账号 `user`、`partner`、`admin`，带本地验证码校验。
- 手机端：用户首页、记录输入、草稿卡片、确认写入、最近记录、绑定管理员积分奖品和绑定用户最近记录。
- 后台端：今日统计、记录列表、记录详情 JSON、记录追踪 JSON。

`admin` 登录进入后台运维端；`user`、`partner` 登录进入手机端，并按后端 `currentViewRole` 展示用户视角或绑定管理员视角。

## 后续开发

新增功能先写 `../docs/future/<功能名>.md`，再进入对应 feature。后台人员能力放 `features/ops`，绑定用户互动能力不要放进 ops。
