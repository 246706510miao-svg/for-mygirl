# record 模块入口

`features/record` 承载普通用户登录后的记录写入主链路：创建会话、发送文本、生成草稿、确认写入、查看本人最近记录和绑定用户最近记录。

## 当前入口

- `api.ts`：
  - `GET /api/user/home`
  - `GET /api/records/recent`
  - `GET /api/bound-user/records/recent`
  - `POST /api/record-sessions`
  - `POST /api/record-sessions/{sessionId}/messages`
  - `GET /api/record-sessions/{sessionId}`
  - `POST /api/record-sessions/{sessionId}/confirm`
- `RecordWorkspace.tsx` 只保留兼容导出，正式手机端页面状态由 `src/app/MobileWorkspace.tsx` 编排。

`messages`、`confirm` 和 `confirm/resume` 会先返回 `workflowStatus=processing`，页面通过 `GET /api/record-sessions/{sessionId}` 轮询 `latestWorkflowTask`、`currentDraft` 和 `pendingConfirmation`，不要在前端等待单个长请求完成 third workflow。

## 排查顺序

1. 页面状态：`src/app/MobileWorkspace.tsx`
2. 接口调用：`api.ts`
3. 通用请求：`../../shared/api/client.ts`
4. 后端入口：`backend/src/main/java/com/formygirl/record/session`
