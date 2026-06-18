# relationship 模块入口

`features/relationship` 承载用户绑定、绑定状态和授权范围。后续“对方能否评论、改风格、管理奖品权利”都先从这里判断。

## 当前入口

- `api.ts`：
  - `GET /api/auth/me`
  - `POST /api/identity/view-role`
  - `GET /api/relationship/binding`
- `src/App.tsx` 使用这些接口决定普通用户进入用户视角还是绑定管理员视角。

## 接入规则

- 不在业务页面里硬编码对方权限。
- 绑定状态和授权范围由后端 `relationship` 模块返回。
- 其他模块只消费授权结果，不直接改绑定数据。
- 手机端“管理员视角”是 `currentViewRole=BOUND_ADMIN`，不是 `OPS_ADMIN`。
