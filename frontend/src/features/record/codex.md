# record 模块入口

`features/record` 承载普通用户登录后的记录写入主链路：创建会话、发送文本、生成草稿、确认写入、查看本人最近记录和绑定用户最近记录。

## 当前入口

- `api.ts`：
  - `GET /api/user/home`
  - `GET /api/records/recent`
  - `GET /api/bound-user/records/recent`
  - `POST /api/record-sessions`
  - `POST /api/record-sessions/{sessionId}/messages`
  - `POST /api/record-sessions/{sessionId}/confirm`
- `RecordWorkspace.tsx` 是保留的开发薄组件；正式手机端页面状态由 `src/App.tsx` 编排。

## 排查顺序

1. 页面状态：`src/App.tsx`
2. 接口调用：`api.ts`
3. 通用请求：`../../shared/api/client.ts`
4. 后端入口：`backend/src/main/java/com/formygirl/record/session`
