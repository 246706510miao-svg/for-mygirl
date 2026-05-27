# 序列图实现约束

## 目标

本项目是个人使用的日常记录 Web 应用。序列图用于约束业务交互顺序，不要按 Controller、Service、Mapper 代码层级重画。

## 当前 MVP 边界

- 用户端：iPhone 移动 Web 或 PWA
- 管理员端：PC Web
- 后端：Java Spring Boot
- 前端语言：TypeScript
- 后端统一调用 AI、ASR、飞书 MCP
- 前端不直接调用外部 AI、ASR、飞书 MCP
- MVP 暂不支持上传背景图或照片
- MVP 暂不引入服务器文件存储模块
- 语音音频只做临时处理，ASR 完成后不长期保存音频

## 序列图清单

必须保持以下业务链路：

1. 用户文本记录生成草稿
2. 用户语音记录生成草稿
3. 用户继续修改草稿
4. 用户确认写入飞书
5. 管理员配置每日内容
6. 用户端加载首页
7. 管理员查看和处理异常

## 关键规则

### 文本和修改指令

文本输入和修改指令统一走：

```http
POST /api/record-sessions/{sessionId}/messages
```

后端保存 RECORD_MESSAGE，并结合历史消息和当前草稿调用 AI，生成新的 RECORD_DRAFT。

### 语音输入

语音输入走：

```http
POST /api/record-sessions/{sessionId}/voice-messages
```

前端只负责录音和上传音频。后端调用 ASR，拿到识别文本后再调用 AI 生成草稿。

### 草稿版本

每次 AI 生成或修改草稿，都必须保存 RECORD_DRAFT。

原因：

- LLM API 本身不会自动保留历史上下文
- 用户可能说“还是刚刚那个版本好”
- 确认写入时需要明确锁定某个草稿版本

### 确认写入

确认写入走：

```http
POST /api/record-sessions/{sessionId}/confirm
```

必须做：

- 检查 clientConfirmId，防止重复提交
- 锁定 RECORD_SESSION
- 锁定当前 RECORD_DRAFT
- 创建 DAILY_RECORD
- 让 AI 生成飞书 MCP Payload
- 后端校验 Payload
- 校验通过后调用飞书 MCP
- 返回 chatReply 和 displayRecord 给前端
- 前端在对话中显示结果，同时刷新最近记录

### 防止死循环

确认写入和管理员重试都不能无限调用 AI 修正 Payload。

建议约束：

- 用户确认写入：最多修正 2 次
- 管理员重试：最多修正 1 到 2 次
- 超过次数后标记为 blocked 或 sync_failed
- 保存 payload、失败原因、错误状态
- 不允许继续递归或无限循环

### 飞书失败

飞书写入失败时不能丢本地记录。

必须保存：

- DAILY_RECORD
- FEISHU_SYNC.payload_json
- FEISHU_SYNC.error_message
- RECORD_DISPLAY 的失败状态

用户端应看到“本地已保存但飞书同步失败”的对话反馈。

### 每日内容

管理员配置每日内容走：

```http
PUT /api/admin/daily-contents
```

模块名称使用“每日内容配置”，不要写成“每日文案配置”。

MVP 支持：

- 文案
- 主题
- 预设背景
- 记录页引导语
- 展示卡片配置

MVP 不支持：

- 上传真实背景图片
- 上传照片文件
- 服务器文件存储

### 首页加载

用户端首页不直接读飞书。

首页数据来自：

- DAILY_CONTENT
- RECORD_DISPLAY
- DAILY_RECORD 状态

## 禁止事项

- 不要让前端直接调用 AI、ASR 或飞书 MCP
- 不要把 API Key、飞书 Token、模型密钥放到前端
- 不要让 AI 生成的 Payload 未校验就执行
- 不要在 confirm 接口中无限循环修复 Payload
- 不要在 MVP 中引入文件上传、对象存储、图床等额外复杂度
- 不要把飞书内容当作用户端直接预览来源
