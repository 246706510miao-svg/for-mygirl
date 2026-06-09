# 第三方服务模块

当前实现是 `workflowagent + Workflow Runtime + Tool` 架构。`third` 可以作为独立 Python 服务运行，SpringBoot 后端后续通过 HTTP 提交 workflow、查询状态、确认后 resume。

## 当前结构

- `agents/workflowagent/`：规划 Agent，接收 `content[0].text`，输出 `workflow_plan`。
- `workflow/`：固定 runtime，负责计划校验、步骤执行、上下文构造、Tool 分发、确认门和最终答案。
- `Tool/`：飞书多维表格 Tool，包括字段读取、查询、新增、更新、删除。
- `storage/`：MySQL/内存 Repository，保存 session、plan、step、artifact、确认和幂等数据。
- `runtime/`：Redis Stream/内存运行态，保存队列、锁、游标、短期 artifact 和幂等缓存。
- `api.py`：FastAPI 入口，提供 workflow 提交、查询、resume。
- `worker.py`：Redis Stream worker，异步执行 workflow。
- `Prompt/workflowagent.yaml`：workflowagent 系统提示词。
- `migrations/`：Alembic migration。
- `docs/`：架构图、ER 图和流程说明。

## 环境变量

飞书配置：

```env
THIRD_FEISHU_USE_REAL=1
THIRD_FEISHU_APP_ID=cli_xxx
THIRD_FEISHU_APP_SECRET=xxx
THIRD_FEISHU_APP_TOKEN=app_xxx
THIRD_FEISHU_TABLE_ID=tbl_xxx
THIRD_FEISHU_VIEW_ID=
THIRD_FEISHU_FIELD_NAME_MAP={}
```

OpenAI 配置：

```env
OPENAI_API_KEY=sk-xxx
THIRD_WORKFLOWAGENT_USE_LLM=1
THIRD_WORKFLOWAGENT_MODEL=gpt-4o-mini
```

存储和异步执行配置：

```env
THIRD_MYSQL_DSN=mysql+pymysql://user:password@mysql:3306/third_service
THIRD_REDIS_URL=redis://redis:6379/0
THIRD_WORKFLOW_QUEUE_NAME=third:workflow:queue
THIRD_WORKFLOW_CONSUMER_GROUP=third-workflow-workers
THIRD_WORKFLOW_CONSUMER_NAME=worker-1
THIRD_WORKFLOW_LOCK_TTL_SECONDS=300
THIRD_WORKFLOW_ARTIFACT_TTL_SECONDS=3600
THIRD_WORKFLOW_IDEMPOTENCY_TTL_SECONDS=604800
THIRD_FEISHU_FIELD_CACHE_TTL_SECONDS=1800
```

说明：没有配置 `THIRD_MYSQL_DSN` 时，代码会使用进程内内存 Repository 兜底；没有可用 Redis 时，会使用进程内内存队列兜底。兜底只适合本地 mock 调试，不适合 SpringBoot 联调或生产。

## 运行方式

安装依赖：

```bash
pip install -r third/requirements.txt
```

执行 MySQL migration：

```bash
cd third
alembic upgrade head
```

启动 API：

```bash
uvicorn third.api:app --host 0.0.0.0 --port 8001
```

启动 worker：

```bash
python -m third.worker
```

同步 LangGraph / LangSmith 调试：

```bash
python -m third.demo "查询状态为进行中的记录，只返回标题、状态"
python -m third.demo "新增一条记录，标题为测试新增，状态为进行中"
```

异步命令行调试：

```bash
python -m third.demo --submit "查询状态为进行中的记录，只返回标题、状态"
python -m third.demo --worker-once
python -m third.demo --status sess_xxx
python -m third.demo --resume sess_xxx --confirmation-id confirm_xxx --approve "确认写入"
```

## API 输入输出

提交 workflow：

```http
POST /workflows/invoke
```

```json
{
  "content": [
    {
      "text": "我今早干了什么，写到飞书里"
    }
  ]
}
```

返回：

```json
{
  "session_id": "sess_xxx",
  "status": "queued",
  "confirmation": null,
  "content": [
    {
      "text": ""
    }
  ],
  "error_text": null
}
```

查询状态：

```http
GET /workflows/{session_id}
```

resume 确认：

```http
POST /workflows/{session_id}/resume
```

```json
{
  "confirmation_id": "confirm_xxx",
  "approved": true,
  "content": [
    {
      "text": "确认写入"
    }
  ]
}
```

## 执行规则

- workflow 异步执行，API 提交后立即返回 `session_id`。
- 每一步结果保存到 `session_artifacts`，后续步骤只读取自己声明依赖的 artifact。
- 写入、更新、删除前必须经过字段读取、字段转换、校验和确认门。
- 写入类操作使用 `idempotency_key` 防止重试造成重复写入。
- 飞书字段定义缓存到 `feishu_field_cache`，通过 `expires_at` 实现 TTL 刷新。
- 当前不做权限传递；飞书访问能力与自建应用配置对齐。

## 常见问题

- `waiting_user`：workflow 正在等待用户确认，调用 `resume` 后继续执行。
- `cancelled`：用户拒绝确认，workflow 不会执行写入。
- `failed`：计划、校验、Tool 或外部服务调用失败，查看 `error_text`。
- 无 MySQL/Redis 时只能做单进程 mock 调试，API 进程和 worker 进程不能共享内存兜底队列。
