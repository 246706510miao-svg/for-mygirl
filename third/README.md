# 第三方服务模块

当前实现是 `workflowagent + Workflow Runtime + Tool` 架构。`third` 可以作为独立 Python 服务运行，SpringBoot 后端后续通过 HTTP 提交 workflow、查询状态、确认后 resume。

## 当前结构

- `agents/workflowagent/`：规划 Agent，接收 `content[0].text`，优先选择 workflow template，再由代码生成 `workflow_plan`。
- `workflow/`：固定 runtime，负责计划校验、步骤执行、上下文构造、Tool 分发、确认门和最终答案。
- `workflow/registry/`：Tool、Agent、Workflow Template 的结构化注册目录；workflowagent 读取这些目录做选择，复杂步骤由模板 builder 生成。
- `Tool/`：飞书多维表格 Tool，包括字段读取、字段变更、查询、新增、更新、删除。
- `storage/`：MySQL/内存 Repository，保存 session、plan、step、artifact、确认和幂等数据。
- `runtime/`：Redis Stream/内存运行态，保存队列、锁、游标、短期 artifact 和幂等缓存。
- `api.py`：FastAPI 入口，提供 workflow 提交、查询、resume。
- `debug/`：本地调试台，展示运行模式、最近 session、步骤时间线、动态图和 artifacts。
- `worker.py`：Redis Stream worker，异步执行 workflow。
- `Dockerfile`：后续服务器部署时，third API、worker、migration 共用镜像。
- `.env.local.docker.example`：本地 Python 连接 Docker MySQL/Redis 的配置模板。
- `.env.docker.mock`：完整 third 容器 profile 的 mock 配置。
- `.env.docker.real.example`：完整 third 容器 profile 的真实飞书配置模板。
- `Prompt/workflowagent.yaml`：workflowagent 系统提示词。
- `Prompt/runagent/`：业务 Agent 提示词文件来源，执行 seed 后写入 MySQL `prompt_registry`。
- `scripts/seed_runagent_prompts.py`：把 `Prompt/runagent/*.yaml` 覆盖同步到 `prompt_registry`。
- `migrations/`：Alembic migration。
- `docs/`：外部调用契约、架构图、ER 图和流程说明。

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

说明：`THIRD_FEISHU_FIELD_NAME_MAP` 用于把用户常用语义字段映射到真实飞书字段名，例如 `{"标题":"事项名称"}`。真实飞书写入时，未映射且不在当前表字段列表中的字段会被拒绝，避免写入错误列。

OpenAI 配置：

```env
OPENAI_API_KEY=sk-xxx
THIRD_WORKFLOWAGENT_USE_LLM=1
THIRD_WORKFLOWAGENT_MODEL=gpt-4o-mini
THIRD_FINAGENT_USE_LLM=0
```

说明：`THIRD_WORKFLOWAGENT_USE_LLM=1` 会同时启用 workflowagent 的模板选择、business_agent 的写入 payload 解析、schema_agent 的字段变更解析，以及 search_agent 的更新/删除候选记录匹配。LLM 模式下，workflowagent 会拿到三类目录：代码内置 Tool 能力目录、代码内置 Workflow Template 目录，以及 MySQL `prompt_registry` 中启用的 Agent 目录。workflowagent 优先输出 `template_key`，由代码模板 builder 生成完整 `workflow_plan.steps`；Agent Runner 执行时再从数据库读取对应 `prompt_text`。数据库没有启用 Agent、缺少对应 prompt、OpenAI 不可用或输出 JSON 非法都会让当前步骤失败，不读取文件兜底。

存储和异步执行配置：

```env
THIRD_MYSQL_DSN=mysql+pymysql://third_user:third_password@127.0.0.1:3307/third_service
THIRD_TEST_MYSQL_DSN=mysql+pymysql://third_user:third_password@127.0.0.1:3307/third_test
THIRD_REDIS_URL=redis://127.0.0.1:6380/0
THIRD_WORKFLOW_QUEUE_NAME=third:workflow:queue
THIRD_WORKFLOW_CONSUMER_GROUP=third-workflow-workers
THIRD_WORKFLOW_CONSUMER_NAME=worker-1
THIRD_WORKFLOW_LOCK_TTL_SECONDS=300
THIRD_WORKFLOW_ARTIFACT_TTL_SECONDS=3600
THIRD_WORKFLOW_IDEMPOTENCY_TTL_SECONDS=604800
THIRD_FEISHU_FIELD_CACHE_TTL_SECONDS=1800
THIRD_ALLOW_IN_MEMORY_FALLBACK=0
THIRD_DEBUG_ENABLED=1
THIRD_WORKFLOW_DEBUG_LOG=1
```

说明：`THIRD_ALLOW_IN_MEMORY_FALLBACK=0` 时，MySQL 或 Redis 缺失会直接报错，不会静默退回进程内内存。Docker、SpringBoot 联调和真实飞书验证建议保持为 `0`。本地单进程 mock 调试才建议设为 `1`。

说明：`THIRD_DEBUG_ENABLED=1` 会启用 `/debug` 调试台；服务器部署时建议设为 `0`，避免暴露 workflow 输入、步骤输出和 artifact 内容。

说明：`THIRD_WORKFLOW_DEBUG_LOG=1` 会在 API/worker 控制台输出 workflowagent 生成的 plan JSON 和失败步骤上下文；未配置时默认跟随 `THIRD_DEBUG_ENABLED`。日志会脱敏 OpenAI、飞书、MySQL、Redis 相关密钥或连接串。

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
alembic upgrade head
```

说明：项目根目录已提供 Alembic 配置，直接从项目根目录执行即可。

同步 runagent 提示词到 MySQL：

```bash
python -m third.scripts.seed_runagent_prompts
```

说明：`Prompt/runagent/` 是维护来源，MySQL `prompt_registry` 是运行时唯一事实来源。当前至少包含 `parse_feishu_record.v1`、`parse_feishu_schema_change.v1` 和 `search_feishu_record.v1`；新增或修改业务 Agent 提示词后，需要重新执行 seed 脚本，同名 `prompt_key` 会覆盖更新。

启动本地 API：

```bash
uvicorn third.api:app --host 0.0.0.0 --port 8001 --reload
```

启动本地 worker：

```bash
python -m third.worker
```

说明：`uvicorn --reload` 可以让 API 进程在代码变化后自动重启；worker 暂时手动重启即可，后续需要也可以引入 watch 工具。`THIRD_WORKFLOW_DEBUG_LOG=1` 时，worker 控制台会打印每个新 workflow 的 plan JSON 和失败步骤信息，便于不打开页面也能定位执行路径。

打开本地调试台：

```text
http://127.0.0.1:8001/debug
```

调试台可以直接提交 workflow、查看最近 session、步骤时间线、动态 Mermaid 文本、artifact、等待确认内容，并在 `waiting_user` 时执行 approve 或 reject。

调试台默认开启自动刷新，但只会在当前 session 为 `queued` 或 `running` 时重绘详情。进入 `waiting_user`、`success`、`failed`、`cancelled` 后会暂停自动重绘，避免查看 `Artifacts` 或 `JSON` 时滚动条被拉回顶部；需要最新数据时点击右上角“刷新”。

调试健康检查：

```http
GET /debug/health
```

它只显示 `configured / missing / ok / error` 等状态，不输出 OpenAI、飞书或数据库密钥明文。真实飞书和 LLM 联调时，先看这里确认 `Feishu real`、`WorkflowAgent LLM`、MySQL、Redis、OpenAI key、飞书表格定位和鉴权配置是否满足要求。

提交一次 workflow：

```bash
curl -X POST http://127.0.0.1:8001/workflows/invoke \
  -H "Content-Type: application/json" \
  -d '{"content":[{"text":"查询记录，只返回事项名称、评级"}]}'
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

只删除并重建 third 私有运行库，不删除 Redis 和 Docker volume。业务库 `for_mygirl_app` 只能由 SpringBoot 管理，不在这里操作：

```bash
docker compose exec mysql mysql -uroot -pthird_root_password -e "DROP DATABASE IF EXISTS third_service; CREATE DATABASE third_service CHARACTER SET utf8mb4 COLLATE utf8mb4_0900_ai_ci; GRANT ALL PRIVILEGES ON third_service.* TO 'third_user'@'%'; FLUSH PRIVILEGES;"
alembic upgrade head
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

真实模式下不会读取 `.env.docker.mock`，也不会把缺失的飞书 `app_token/table_id` 替换成 mock 默认值。飞书配置缺失、字段读取失败或接口失败时，workflow 会返回错误状态。字段变更还要求飞书自建应用具备多维表格字段管理权限；权限不足时字段 Tool 会返回飞书接口错误。

### 同步 LangGraph / LangSmith 调试

```bash
python -m third.demo "查询记录，只返回事项名称、评级"
python -m third.demo "新增一条记录，事项名称为测试新增，总结为联调记录，评级为A"
```

异步命令行调试：

```bash
python -m third.demo --submit "查询记录，只返回事项名称、评级"
python -m third.demo --worker-once
python -m third.demo --status sess_xxx
python -m third.demo --resume sess_xxx --confirmation-id confirm_xxx --approve "确认写入"
```

## API 输入输出

正式对接前先阅读 `docs/外部调用契约.md`。默认正式调用是 agent-led：外部系统把用户原始内容放入 `content[0].text`，由 workflowagent 决定查询、草稿、写入、更新、删除或改字段；SpringBoot 保存 third session 映射、转发 confirmation/resume，并优先消费 snapshot。`metadata.operation` 只用于特殊 override，普通前端消息接口不要传。

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
  ],
  "metadata": {
    "businessSessionId": "session_xxx",
    "idempotencyKey": "cmid_xxx"
  }
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

读取统一快照：

```http
GET /internal/workflows/{session_id}/snapshot
```

snapshot 返回 `session`、`decision`、`confirmation`、`outputs`、`artifactsByKey`。后端读取 `outputs.draft`、`outputs.writePayload`、`outputs.writeResult`、`outputs.finalAnswer` 等稳定字段，并把完整 JSON 保存到 trace/sync payload；前端不直接消费 third artifact key。

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

## Debug API

调试接口只属于 `third` 本地开发层，不需要 SpringBoot 代理才能使用。关闭 `THIRD_DEBUG_ENABLED` 后，除标准 `/health` 外，调试页面和调试数据接口不可访问。

```http
GET /debug
GET /debug/health
GET /debug/workflows?limit=50
GET /debug/workflows/latest
GET /debug/workflows/{session_id}/timeline
GET /debug/workflows/{session_id}/artifacts
GET /debug/workflows/{session_id}/graph
```

`/debug/workflows/{session_id}/timeline` 会从现有 MySQL 表推导执行过程，不依赖新增事件表。读取类 workflow 通常直接到 `success`；新增、更新、删除和字段变更会先停在 `waiting_user`，调试台确认后 worker 才会继续执行有副作用的 Tool。

页面顶部“自动刷新”开关用于控制当前 session 详情轮询。关闭后页面不再自动请求详情接口；手动刷新仍会更新运行模式、最近 session 和当前详情，并尽量保留 `Artifacts`、`JSON` 视图的滚动位置。

## 执行规则

- workflow 异步执行，API 提交后立即返回 `session_id`。
- 每一步结果保存到 `session_artifacts`，后续步骤只读取自己声明依赖的 artifact。
- 调试台只读取实际写入的 session、plan、step、artifact、confirmation，因此同时兼容 mock、真实飞书、规则 workflowagent 和 LLM workflowagent。
- 如果 LLM 生成的 `workflow_plan` 未通过校验，executor 会保存 `workflow.plan.invalid` artifact，里面包含校验错误和原始 plan，便于定位模型漏字段或误判意图。
- 调试日志由 `THIRD_WORKFLOW_DEBUG_LOG` 控制，本地开启时会输出脱敏后的 workflow plan、无效 plan 和失败 step 摘要。
- `THIRD_WORKFLOWAGENT_USE_LLM=1` 时，workflowagent 只能从注入的 Tool 能力目录、Workflow Template 目录和数据库 Agent 目录中选择能力；复杂流程优先输出 `template_key`，由代码模板 builder 生成步骤。
- `THIRD_WORKFLOWAGENT_USE_LLM=0` 时，保留规则 workflowagent 和规则 payload 解析，用于 mock 或离线调试。
- 写入、更新、删除前必须经过字段读取、字段转换、校验和确认门。
- 字段变更走同一套 workflow runtime，不新建执行流；典型步骤是 `read_schema -> schema_agent -> schema_validation -> confirm -> change_fields_tool -> refresh_schema`。
- 用户一句话同时要求改字段再写记录时，先确认并执行字段变更，刷新 schema 后再进入现有记录写入链路和写入确认门。
- business_agent 只生成候选业务 payload；新增可输出批量 `create_request.records`，更新/删除会额外生成候选读取 payload。
- schema_agent 只生成候选字段变更 payload；字段是否重复、字段类型、删除字段风险、确认预览和最终 Tool 入参由 validation 节点确定。
- 更新和删除会先调用 `tool_ReadFeishuBitable` 读取候选记录，再由 `search_agent/search_feishu_record.v1` 从候选中匹配 `record_id`；低置信匹配也会进入确认门，但确认文本和 preview 会显示置信度、理由和备选候选。
- 字段是否存在、类型转换、匹配到的 `record_id`、确认预览和最终 Tool 入参由 validation 节点确定，写入 Tool 还会二次 normalize。
- 写入类操作使用 `idempotency_key` 防止重试造成重复写入。
- 飞书字段定义缓存到 `feishu_field_cache`，通过 `expires_at` 实现 TTL 刷新；字段变更成功后会立即刷新字段缓存，避免后续记录写入继续使用旧 schema。
- 当前不做权限传递；飞书访问能力与自建应用配置对齐。

## 常见问题

- `waiting_user`：workflow 正在等待用户确认，调用 `resume` 后继续执行。
- `cancelled`：用户拒绝确认，workflow 不会执行写入。
- `failed`：计划、校验、Tool 或外部服务调用失败，查看 `error_text`。
- 无 MySQL/Redis 时只能做单进程 mock 调试，API 进程和 worker 进程不能共享内存兜底队列。
