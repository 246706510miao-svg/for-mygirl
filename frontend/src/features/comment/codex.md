# comment 模块入口

`features/comment` 承载绑定管理员对记录的评论和打分。评论和打分只展示和保存到本地业务库，不进入飞书。

## 当前入口

- `api.ts`：`POST /api/records/{recordId}/comment`。
- 页面状态目前由 `src/App.tsx` 的绑定用户最近记录页编排。

## 接入规则

- 评论必须关联 `recordId` 和作者。
- 只有切换到 `BOUND_ADMIN` 的绑定用户可以评论和打分。
- 保存打分会触发后端积分差额入账，前端不要自行计算积分。
- 评论列表可以嵌入记录详情，但 API 和状态仍留在本模块。
