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
- `Dockerfile`：后续服务器部署时，third API、worker、migration 共用镜像。
- `.env.local.docker.example`：本地 Python 连接 Docker MySQL/Redis 的配置模板。
- `.env.docker.mock`：完整 third 容器 profile 的 mock 配置。
- `.env.docker.real.example`：完整 third 容器 profile 的真实飞书配置模板。
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
THIRD_FINAGENT_USE_LLM=0
```

存储和异步执行配置：

```env
THIRD_MYSQL_DSN=mysql+pymysql://third_user:third_password@127.0.0.1:3307/third_service
THIRD_REDIS_URL=redis://127.0.0.1:6380/0
THIRD_WORKFLOW_QUEUE_NAME=third:workflow:queue
THIRD_WORKFLOW_CONSUMER_GROUP=third-workflow-workers
THIRD_WORKFLOW_CONSUMER_NAME=worker-1
THIRD_WORKFLOW_LOCK_TTL_SECONDS=300
THIRD_WORKFLOW_ARTIFACT_TTL_SECONDS=3600
THIRD_WORKFLOW_IDEMPOTENCY_TTL_SECONDS=604800
THIRD_FEISHU_FIELD_CACHE_TTL_SECONDS=1800
THIRD_ALLOW_IN_MEMORY_FALLBACK=0
```

说明：`THIRD_ALLOW_IN_MEMORY_FALLBACK=0` 时，MySQL 或 Redis 缺失会直接报错，不会静默退回进程内内存。Docker、SpringBoot 联调和真实飞书验证建议保持为 `0`。本地单进程 mock 调试才建议设为 `1`。

## 运行方式

### 本地开发：Docker 只启动 MySQL/Redis

当前阶段推荐这种方式：数据库和 Redis 由 Docker 管理，`third` 代码仍然在本机 Python 进程里运行。这样改 `third` 代码后不用重新 build 镜像，重启本地 API/worker 即可。

```bash
docker compose up -d
```

默认宿主机端口：MySQL `3307`、Redis `6380`。

查看服务状态：

```bash
docker compose ps
docker compose logs -f mysql redis
```

准备本地 env：

```powershell
Copy-Item third/.env.local.docker.example third/.env
```

安装依赖：

```bash
pip install -r third/requirements.txt
```

执行 MySQL migration：

```bash
cd third
alembic upgrade head
cd ..
```

启动本地 API：

```bash
uvicorn third.api:app --host 0.0.0.0 --port 8001 --reload
```

启动本地 worker：

```bash
python -m third.worker
```

说明：`uvicorn --reload` 可以让 API 进程在代码变化后自动重启；worker 暂时手动重启即可，后续需要也可以引入 watch 工具。

提交一次 workflow：

```bash
curl -X POST http://127.0.0.1:8001/workflows/invoke \
  -H "Content-Type: application/json" \
  -d '{"content":[{"text":"查询状态为进行中的记录，只返回标题、状态"}]}'
```

查询状态：

```bash
curl http://127.0.0.1:8001/workflows/sess_xxx
```

写入类请求会进入 `waiting_user`，需要调用 resume：

```bash
curl -X POST http://127.0.0.1:8001/workflows/sess_xxx/resume \
  -H "Content-Type: application/json" \
  -d '{"confirmation_id":"confirm_xxx","approved":true,"content":[{"text":"确认写入"}]}'
```

停止服务：

```bash
docker compose down
```

清空本地 MySQL/Redis 数据卷：

```bash
docker compose down -v
```

只删除并重建 MySQL 业务库，不删除 Redis 和 Docker volume：

```bash
docker compose exec mysql mysql -uroot -pthird_root_password -e "DROP DATABASE IF EXISTS third_service; CREATE DATABASE third_service CHARACTER SET utf8mb4 COLLATE utf8mb4_0900_ai_ci; GRANT ALL PRIVILEGES ON third_service.* TO 'third_user'@'%'; FLUSH PRIVILEGES;"
cd third
alembic upgrade head
cd ..
```

### 完整 third 容器验证

这不是当前推荐的本地开发方式，主要用于后续服务器部署或完整容器链路验证。使用 profile 后才会 build third 镜像：

```bash
docker compose --profile third-container up -d --build
```

mock 模式默认使用 `third/.env.docker.mock`。

真实飞书容器验证时，复制 `third/.env.docker.real.example` 为本地私有 env 文件，填入真实飞书和 OpenAI 配置，然后让 Compose 只加载这个文件：

```powershell
$env:THIRD_ENV_FILE = "./third/.env.docker.real"
docker compose --profile third-container up -d --build
```

真实模式必须设置：

```env
THIRD_FEISHU_USE_REAL=1
THIRD_FEISHU_APP_ID=cli_xxx
THIRD_FEISHU_APP_SECRET=xxx
THIRD_FEISHU_APP_TOKEN=app_xxx
THIRD_FEISHU_TABLE_ID=tbl_xxx
OPENAI_API_KEY=sk_xxx
THIRD_WORKFLOWAGENT_USE_LLM=1
THIRD_FINAGENT_USE_LLM=0
THIRD_ALLOW_IN_MEMORY_FALLBACK=0
```

真实模式下不会读取 `.env.docker.mock`，也不会把缺失的飞书 `app_token/table_id` 替换成 mock 默认值。飞书配置缺失、字段读取失败或接口失败时，workflow 会返回错误状态。

### 同步 LangGraph / LangSmith 调试

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
