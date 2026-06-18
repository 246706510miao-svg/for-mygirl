# frontend 初始化说明

`frontend` 是 Vite React TypeScript 前端。第一版以接口联调为主，页面内容按 `docs/接口文档.md` 的返回结构展示，详细组件和视觉内容后续补充。

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

后端默认地址是：

```text
http://localhost:8080
```

如需覆盖：

```powershell
$env:VITE_API_BASE_URL = "http://localhost:8080"
npm run dev
```

## 构建

```powershell
npm run build
```

## 当前页面

- 用户端：用户首页、记录输入、草稿卡片、确认写入、最近记录。
- 管理员端：今日统计、记录列表、记录详情 JSON、记录追踪 JSON。

第一版自动使用 dev 账号登录，不提供正式登录页。
