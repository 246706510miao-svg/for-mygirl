# workflowagent 到 Tool 工作流程

## 1. 用户输入

公开输入仍然只使用 `content[0].text`。

```json
{
  "content": [
    {
      "text": "新增一条记录，事项名称为测试新增，总结为联调记录，评级为A"
    }
  ]
}
```

## 2. workflowagent 生成计划

`workflowagent` 不直接调用 Tool，也不直接写入飞书。它输出 `workflow_plan`，说明每一步要做什么、输入来自哪里、输出保存到哪个 artifact。

新增类计划会包含：

1. `tool_ReadFeishuBitableSchema`：读取字段定义，保存为 `feishu.table_schema`。
2. `business_agent`：使用数据库 Agent 目录中 `prompt_ref=parse_feishu_record.v1` 的提示词，把用户输入转换成飞书写入 payload，保存为 `feishu.create_payload`。
3. `validation`：校验字段、类型和定位条件，保存为 `validation.write_payload`。
4. `confirm`：生成确认请求，状态进入 `waiting_user`。
5. `tool_CreateFeishuBitableRecord`：用户确认后执行写入，保存为 `write_result`。

更新和删除类计划会在 `business_agent` 后多两步：

1. `tool_ReadFeishuBitable`：使用 `candidate_read_payload` 读取候选记录，保存为 `feishu.candidate_records`。
2. `search_agent`：使用数据库 Agent 目录中 `prompt_ref=search_feishu_record.v1` 的提示词，从候选记录中匹配目标 `record_id`，保存为 `feishu.record_match`。

随后 `validation` 会同时读取字段 schema、业务 payload 和 `feishu.record_match`，把匹配出的 `record_id` 合并进最终 Tool 请求。

## 3. Runtime 执行步骤

`Workflow Executor` 是确定性执行器。它按 `workflow_plan.steps` 逐步执行，每一步执行前由 `Step Context Builder` 只读取当前步骤需要的 artifact。

示例：校验步骤只读取：

```json
{
  "from_session": [
    "feishu.table_schema",
    "feishu.create_payload"
  ]
}
```

说明：业务 Agent 每一轮都是无状态的，记忆来自 `session_artifacts`。LLM 模式下，workflowagent 只能选择 MySQL `prompt_registry` 中启用的 `agent_name/prompt_ref`；Agent Runner 也只从数据库读取提示词正文。

业务 Agent 不直接调用写入 Tool，也不直接决定飞书 HTTP 字段。`business_agent` 根据用户原话和 `feishu.table_schema` 生成候选业务 payload；新增请求中如果用户描述多个独立事项，可以输出 `create_request.records`。更新或删除时，`business_agent` 只提供粗定位或显式 `record_id`，系统会先读取候选记录，再由 `search_agent` 做语义匹配。字段名、字段类型、单选选项、日期/数字转换、匹配出的 `record_id`、确认预览和幂等 key 都由后续 `validation` 节点确定；写入 Tool 在真正调用飞书前还会再次 normalize。

## 4. Tool 输入输出

所有 Tool 仍然使用 `content[0].text` 外壳。Runtime 会把 artifact 转换成 Tool 需要的结构化 JSON。

写入 Tool 输入示例：

```json
{
  "original_input": "新增一条记录，事项名称为测试新增，总结为联调记录，评级为A",
  "create_request": {
    "operation": "create_record",
    "service": "feishu_bitable",
    "fields": {
      "事项名称": "测试新增",
      "总结": "联调记录",
        "评级": "A"
      }
    }
  }
```

Tool 输出仍然是 `tool_result`：

```json
{
  "type": "tool_result",
  "tool_name": "tool_CreateFeishuBitableRecord",
  "operation": "create_record",
  "record_count": 1,
  "record": {
    "record_id": "rec_xxx"
  }
}
```

## 5. 用户确认

新增、更新、删除默认不会直接写入。Confirm Gate 会创建确认请求：

```json
{
  "session_id": "sess_xxx",
  "status": "waiting_user",
  "confirmation": {
    "confirmation_id": "confirm_xxx",
    "request_text": "确认执行以下飞书写入操作吗？",
    "preview_json": {
      "fields": {
        "事项名称": "测试新增",
        "总结": "联调记录",
        "评级": "A"
      }
    }
  },
  "content": [
    {
      "text": ""
    }
  ]
}
```

更新或删除如果经过 `search_agent` 匹配，`preview_json` 还会包含 `match_info`，展示目标 `record_id`、置信度、匹配理由和备选候选。低置信匹配不会自动失败，但 `request_text` 会提示“低置信匹配，请核对后再确认”；用户拒绝后不会执行写入 Tool。

SpringBoot 后续调用 `POST /workflows/{session_id}/resume` 后，worker 会继续执行剩余步骤。

## 6. 最终返回

workflow 完成后，最终答案保存到 `workflow_sessions.final_answer`，查询接口返回：

```json
{
  "session_id": "sess_xxx",
  "status": "success",
  "content": [
    {
      "text": "已在 mock 飞书表新增 1 条记录，record_id：rec_xxx。"
    }
  ]
}
```

简短流程：

```text
用户 content[0].text -> workflowagent 生成计划 -> executor 动态执行步骤 -> artifact 记忆 -> confirm gate -> Tool -> final answer
```

## 7. 调试 Demo

本地 API 启动后，可以打开：

```text
http://127.0.0.1:8001/debug
```

调试台直接调用 `third` 的 API，不需要 SpringBoot 参与。它展示：

1. `/debug/health`：当前是 mock 还是真实飞书、规则还是 LLM workflowagent、MySQL/Redis 是否可用、OpenAI key 和飞书配置是否存在。
2. 最近 session：查看历史 workflow，不需要手动复制 `session_id` 后 curl。
3. 时间线：按 `workflow_plan.steps` 展示每一步的 kind、tool/agent、状态、耗时、输出 key、错误信息。
4. 动态图：根据当前 workflow 的步骤生成 Mermaid 文本和页面节点链。
5. Artifacts：查看每一步保存到 `session_artifacts` 的输入输出结果。
6. Confirm Gate：`waiting_user` 时在页面里 approve 或 reject。

调试台只读取现有表：

```text
workflow_sessions -> workflow_plans -> workflow_steps -> session_artifacts -> workflow_confirmations
```

因此它同时兼容 mock、真实飞书、规则 workflowagent 和 LLM workflowagent。真实模式下如果字段、权限、飞书接口、Agent 目录或 LLM 计划出错，失败步骤和 artifact 会保留错误信息。LLM plan 未通过校验时会额外保存 `workflow.plan.invalid` artifact，记录原始 plan 和校验错误。

## 8. 本地 Docker 数据库和真实模式边界

当前本地开发默认只用 Docker 启动 MySQL 和 Redis：

```bash
docker compose up -d
```

本地 `third` API 和 worker 连接宿主机端口：

```env
THIRD_MYSQL_DSN=mysql+pymysql://third_user:third_password@127.0.0.1:3307/third_service
THIRD_REDIS_URL=redis://127.0.0.1:6380/0
THIRD_ALLOW_IN_MEMORY_FALLBACK=0
```

这种模式不构建 third 镜像，改 `third` 代码后只需要重启本地 Python 进程。API 可以用 `uvicorn --reload` 自动重启。

需要清空并重建 MySQL 业务库时，先删除 `third_service`，再重新执行 Alembic：

```bash
docker compose exec mysql mysql -uroot -pthird_root_password -e "DROP DATABASE IF EXISTS third_service; CREATE DATABASE third_service CHARACTER SET utf8mb4 COLLATE utf8mb4_0900_ai_ci; GRANT ALL PRIVILEGES ON third_service.* TO 'third_user'@'%'; FLUSH PRIVILEGES;"
alembic upgrade head
```

真实飞书验证时，在本地 `third/.env` 中设置：

```env
THIRD_FEISHU_USE_REAL=1
THIRD_FEISHU_APP_ID=cli_xxx
THIRD_FEISHU_APP_SECRET=xxx
THIRD_FEISHU_APP_TOKEN=app_xxx
THIRD_FEISHU_TABLE_ID=tbl_xxx
```

真实模式下，Tool 不会读取 mock 记录，也不会把缺失的飞书表格定位替换成 mock 默认值。配置缺失或飞书接口失败时，错误会保存到 workflow 状态并返回给调用方。

后续服务器部署或完整容器链路验证时，再使用：

```bash
docker compose --profile third-container up -d --build
```
