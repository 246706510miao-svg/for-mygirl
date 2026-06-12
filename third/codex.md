# third 模块目录结构

## 阅读顺序

1. `README.md`：先看模块目标、运行方式、API 和环境变量。
2. `docs/总架构图.md`：查看 SpringBoot、third、Redis、MySQL、OpenAI、飞书之间的边界。
3. `docs/workflow-db-er.md`：查看 MySQL 表、Redis key、字段缓存 TTL 和幂等规则。
4. `docs/workflowagent-fixed-graph.md`：查看固定执行图和每个节点职责。
5. `docs/router-read00.md`：查看当前 workflowagent 到 Tool 的输入输出流程。
6. `agents/graph.py`、`workflow/executor.py`：理解 LangGraph 固定入口和 runtime 执行方式。
7. `agents/workflowagent/agent.py`、`Prompt/workflowagent.yaml`：查看动态计划生成逻辑和提示词。
8. `Prompt/runagent/`、`scripts/seed_runagent_prompts.py`：查看业务 Agent 提示词文件来源和同步到数据库的脚本。
9. `workflow/agent_runner.py`：查看 business_agent、search_agent 按 `prompt_ref` 从数据库读取提示词并执行的逻辑。
10. `Tool/`：查看飞书字段读取、查询、新增、更新、删除 Tool。
11. `storage/`、`runtime/`：查看 MySQL Repository 和 Redis Stream 运行态。
10. `debug/`：查看本地调试台、运行模式体检、时间线和动态图生成。
11. `api.py`、`worker.py`：查看 SpringBoot 后续要调用的 API 和 worker 消费入口。
12. `../docker-compose.yml`、`.env.local.docker.example`：查看本地 MySQL/Redis Docker 验证入口。
13. `Dockerfile`、`.env.docker.mock`：查看后续完整 third 容器部署入口。

## 目录结构

```text
third/
|-- README.md                         # 模块说明、配置项、API、运行方式
|-- codex.md                          # 当前目录说明
|-- langgraph.json                    # LangGraph / LangSmith 加载图配置
|-- pyproject.toml                    # Python 包配置
|-- requirements.txt                  # 运行依赖
|-- .env.example                      # 环境变量示例
|-- .env.local.docker.example         # 本地 Python 连接 Docker MySQL/Redis 的模板
|-- .env.docker.mock                  # 完整 third 容器 profile 的 mock 环境
|-- .env.docker.real.example          # 完整 third 容器 profile 的真实飞书模板
|-- Dockerfile                        # 后续部署用 third API、worker、migration 共用镜像
|-- alembic.ini                       # Alembic migration 主配置
|-- api.py                            # FastAPI Workflow API
|-- worker.py                         # Redis Stream workflow worker
|-- demo.py                           # 同步和异步命令行调试入口
|-- debug/
|   |-- router.py                     # /debug 页面、健康检查、timeline、graph、artifacts 接口
|   |-- page.py                       # 内置调试台 HTML
|   `-- __init__.py
|-- agents/
|   |-- graph.py                      # LangGraph 固定入口，调用 workflow runtime
|   |-- state.py                      # LangGraph 公开输入输出状态
|   |-- workflowagent/
|   |   |-- agent.py                  # workflowagent，生成动态 workflow_plan
|   |   `-- __init__.py
|   |-- finagent/                     # 旧 finagent 兼容代码，当前主流程不优先看这里
|   `-- shared/
|       |-- config.py                 # 飞书、OpenAI、MySQL、Redis、workflow 环境配置
|       |-- feishu_schema.py          # 飞书字段结构辅助
|       |-- mock_feishu.py            # mock 飞书数据
|       `-- time_utils.py             # 时间工具
|-- Prompt/
|   |-- workflowagent.yaml            # workflowagent 系统提示词
|   |-- runagent/                     # 业务 Agent 提示词文件来源，seed 后写入 prompt_registry
|   |-- finagent.yaml                 # 旧 finagent 提示词兼容文件
|   `-- __init__.py
|-- scripts/
|   `-- seed_runagent_prompts.py      # runagent 提示词同步脚本
|-- Tool/
|   |-- feishu_client.py              # 飞书 OpenAPI HTTP 客户端
|   |-- field_context.py              # 字段上下文读取，接入 TTL 字段缓存
|   |-- mock_repository.py            # mock 多维表格 CRUD 逻辑
|   |-- tool_ReadFeishuBitableSchema.py
|   |-- tool_ReadFeishuBitable.py
|   |-- tool_CreateFeishuBitableRecord.py
|   |-- tool_UpdateFeishuBitableRecord.py
|   |-- tool_DeleteFeishuBitableRecord.py
|   `-- write_support.py              # 写入类 Tool 共用字段校验和值转换逻辑
|-- workflow/
|   |-- executor.py                   # workflow 执行器
|   |-- plan_validator.py             # workflow_plan 校验
|   |-- tool_dispatcher.py            # Tool 分发
|   |-- agent_runner.py               # 业务 Agent 执行封装，支持 payload 解析和候选记录匹配
|   |-- content.py                    # content[0].text 输入输出辅助
|   |-- field_cache.py                # 飞书字段缓存逻辑
|   |-- validation.py                 # 写入确认和幂等校验
|   `-- api_schema.py                 # API 输入输出结构
|-- storage/
|   |-- database.py                   # SQLAlchemy Engine、Session 和本地建表辅助
|   |-- factory.py                    # MySQL Repository / 内存 Repository 创建入口
|   |-- models.py                     # workflow MySQL 表模型
|   `-- repository.py                 # workflow 数据读写 Repository
|-- runtime/
|   |-- factory.py                    # Redis 运行态 / 内存运行态创建入口
|   `-- redis_runtime.py              # Redis Stream、锁、artifact、幂等缓存封装
|-- migrations/
|   |-- env.py                        # Alembic 从 THIRD_MYSQL_DSN 注入数据库 URL
|   `-- versions/
|       `-- 0001_workflow_tables.py   # workflow 首版建表 migration
`-- docs/
    |-- 总架构图.md
    |-- workflow-db-er.md
    |-- workflowagent-fixed-graph.md
    `-- router-read00.md
```

## 数据库配置入口

- MySQL 连接串配置在 `.env` 或项目根目录 `.env` 的 `THIRD_MYSQL_DSN`。
- Redis 连接串配置在 `.env` 或项目根目录 `.env` 的 `THIRD_REDIS_URL`。
- 本地开发时，Docker 只启动 MySQL/Redis，`third` 本地 Python 进程连接 `127.0.0.1:3307` 和 `127.0.0.1:6380`。
- 完整 third 容器验证时，Compose profile 读取 `.env.docker.mock`；真实飞书验证时用 `THIRD_ENV_FILE` 指向你的私有 env 文件。
- 配置读取入口是 `agents/shared/config.py` 的 `load_config()`。
- MySQL Engine 创建入口是 `storage/database.py` 的 `create_workflow_engine()`。
- Redis 运行态创建入口是 `runtime/factory.py` 的 `get_workflow_runtime_store()`。
- 建表脚本在 `migrations/versions/0001_workflow_tables.py`。
- `THIRD_ALLOW_IN_MEMORY_FALLBACK=0` 会禁止 MySQL/Redis 失败时回退到进程内内存，Docker 和真实联调建议保持为 `0`。
- `THIRD_DEBUG_ENABLED=1` 会启用 `/debug` 调试台，本地默认开启，服务器部署建议关闭。
- `THIRD_WORKFLOW_DEBUG_LOG=1` 会输出脱敏后的 workflow plan JSON 和失败步骤摘要；未配置时默认跟随 `THIRD_DEBUG_ENABLED`。

## 建表方式

生产和联调环境优先使用 Alembic：

```bash
alembic upgrade head
```

项目根目录和 `third/` 目录都保留 Alembic 配置；推荐从项目根目录执行上面的命令。

重建本地 Docker MySQL 业务库时，可以先删除并重建 `third_service`，再重新执行 Alembic：

```bash
docker compose exec mysql mysql -uroot -pthird_root_password -e "DROP DATABASE IF EXISTS third_service; CREATE DATABASE third_service CHARACTER SET utf8mb4 COLLATE utf8mb4_0900_ai_ci; GRANT ALL PRIVILEGES ON third_service.* TO 'third_user'@'%'; FLUSH PRIVILEGES;"
alembic upgrade head
```

本地临时调试也可以调用 `storage/database.py` 里的 `create_all_tables()`，但正式流程不要依赖它，后续表结构演进应继续走 Alembic migration。

## Docker Compose 验证入口

本地开发默认只启动 MySQL/Redis：

```bash
docker compose up -d
```

本地启动 API 时可以使用 reload：

```bash
uvicorn third.api:app --host 0.0.0.0 --port 8001 --reload
```

本地调试台入口：

```text
http://127.0.0.1:8001/debug
```

调试台读取现有 workflow 表生成时间线和 Mermaid 文本，不新增数据库表。真实飞书和 LLM 联调时，先看 `/debug/health` 的 Feishu、WorkflowAgent、OpenAI、MySQL、Redis 和内存兜底状态。

调试台默认只在当前 session 处于 `queued` 或 `running` 时自动刷新详情；进入 `waiting_user`、`success`、`failed`、`cancelled` 后会暂停自动重绘，避免查看 `Artifacts` 或 `JSON` 时滚动位置被重置。需要最新数据时使用页面右上角“刷新”。

本地 worker 使用标准 logging，`python -m third.worker` 会在 `THIRD_WORKFLOW_DEBUG_LOG=1` 时打印 workflowagent 生成的 plan JSON 和失败步骤上下文，日志会脱敏密钥、token、DSN 和 Redis URL。

后续完整 third 容器验证：

```bash
docker compose --profile third-container up -d --build
```

完整 third 容器真实飞书验证：

```powershell
$env:THIRD_ENV_FILE = "./third/.env.docker.real"
docker compose --profile third-container up -d --build
```

说明：默认本地开发不会构建 third 镜像。只有使用 `third-container` profile 时，才会构建并运行 third API、worker 和 migration 容器。
