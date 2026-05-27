# 接口实现约束

## 总目标

实现日常记录 Web 应用的 MVP 接口。接口应服务于当前业务闭环，不要主动扩展复杂功能。

## 技术边界

- 前端：TypeScript Web
- 用户端：iPhone 移动 Web 或 PWA
- 管理员端：PC Web
- 后端：Java Spring Boot

## 禁止越界

前端禁止：

- 直接调用大模型
- 直接调用语音识别服务
- 直接调用飞书 MCP
- 保存任何 API Key、Token、模型密钥

后端禁止：

- 把可变配置硬编码在业务逻辑里
- 未校验就执行 AI 生成的 MCP Payload
- confirm 接口无限循环修复 Payload
- retry-sync 接口无限循环重试
- 将数据库端口暴露公网

## MVP 暂不做

不要实现以下功能：

- 上传背景图
- 上传照片
- 服务器文件存储
- 长期保存语音音频
- 原生 iOS App
- 小程序
- 复杂多用户权限系统
- 管理员统计图表
- 飞书内容直接预览
- 多服务器部署
- 消息队列

## API 设计原则

### 统一返回 chatReply

用户侧与对话相关的接口必须返回 chatReply：

- 提交文本
- 提交语音
- 修改草稿
- 确认写入

前端需要在对话中展示 AI 或系统返回，而不是只刷新列表。

### confirm 必须幂等

确认写入接口：

```http
POST /api/record-sessions/{sessionId}/confirm
```

必须使用 clientConfirmId 做幂等控制。

重复请求不能：

- 创建多条 DAILY_RECORD
- 多次写入飞书
- 产生多个正式记录

### AI 修正次数限制

确认写入：

- AI 生成 MCP Payload 后，后端校验
- 如果校验失败，可以要求 AI 修正
- 最多修正 2 次
- 超过次数后标记为 blocked 或 sync_failed

管理员重试：

- AI 修正 Payload 最多 1 到 2 次
- 失败后保存错误原因
- 不继续递归

### 飞书失败不能丢记录

飞书失败时仍然要保存：

- DAILY_RECORD
- FEISHU_SYNC.payload_json
- FEISHU_SYNC.error_message
- RECORD_DISPLAY 的失败状态

用户端返回：

- syncStatus = failed
- chatReply 说明本地已保存但飞书同步失败
- displayRecord 用于刷新最近记录

### 语音处理

语音接口：

```http
POST /api/record-sessions/{sessionId}/voice-messages
```

必须遵守：

- 前端只录音和上传
- 后端调用 ASR
- MVP 不长期保存音频
- 数据库保存 asrText
- 返回 asrText、draft、chatReply

### 每日内容配置

接口：

```http
PUT /api/admin/daily-contents
```

模块名必须是“每日内容配置”。

MVP 支持：

- homeText
- theme
- backgroundPreset
- recordGuide
- card
- reminder

MVP 不支持上传真实图片。

### 首页数据

用户首页接口：

```http
GET /api/user/home
```

数据来源：

- DAILY_CONTENT
- RECORD_DISPLAY
- DAILY_RECORD 状态

禁止直接读取飞书作为用户端展示源。

## 推荐状态值

### RECORD_SESSION.status

- editing
- previewing
- confirming
- confirmed
- cancelled

### DAILY_RECORD.status

- success
- sync_failed
- blocked

### FEISHU_SYNC.sync_status

- pending
- success
- failed

## 接口清单

用户端：

- GET /api/user/home
- POST /api/record-sessions
- POST /api/record-sessions/{sessionId}/messages
- POST /api/record-sessions/{sessionId}/voice-messages
- GET /api/record-sessions/{sessionId}
- POST /api/record-sessions/{sessionId}/confirm
- POST /api/record-sessions/{sessionId}/cancel

管理员端：

- GET /api/admin/records
- GET /api/admin/records/{recordId}
- GET /api/admin/daily-contents
- PUT /api/admin/daily-contents
- POST /api/admin/records/{recordId}/retry-sync
- PATCH /api/admin/records/{recordId}/display

## 实现顺序建议

1. 创建记录会话
2. 提交文本生成草稿
3. 查询记录会话
4. 确认写入但先 mock 飞书
5. 接入真实飞书 MCP
6. 接入语音识别
7. 加管理员每日内容配置
8. 加异常记录重试
