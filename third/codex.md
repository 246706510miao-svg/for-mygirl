# third 模块目录表

## 阅读顺序

1. `README.md`：先看模块目标、运行方式、API 和环境变量。
2. `docs/总架构图.md`：查看 SpringBoot、third、Redis、MySQL、OpenAI、飞书之间的边界。
3. `docs/workflow-db-er.md`：查看 MySQL 表、Redis key、字段缓存 TTL 和幂等规则。
4. `docs/router-read00.md`：查看当前 workflowagent 到 Tool 的输入输出流程。
5. `agents/graph.py`、`workflow/executor.py`：理解 LangGraph 固定入口和 runtime 执行方式。
6. `agents/workflowagent/agent.py`、`Prompt/workflowagent.yaml`：查看动态计划生成逻辑和提示词。
7. `Tool/`：查看飞书字段读取、查询、新增、更新、删除 Tool。
8. `storage/`、`runtime/`：查看 MySQL Repository 和 Redis Stream 运行态。
9. `api.py`、`worker.py`：查看 SpringBoot 后续要调用的 API 和 worker 消费入口。

## 目录表

| 路径 | 用途 |
| --- | --- |
| `README.md` | 模块说明、配置项、API、运行方式。 |
| `codex.md` | 当前目录表。 |
| `docs/总架构图.md` | third 总览架构图。 |
| `docs/workflow-db-er.md` | workflow 数据库 ER 图和 Redis key 设计。 |
| `docs/workflowagent-fixed-graph.md` | 固定执行图和节点职责说明。 |
| `docs/router-read00.md` | workflowagent 到 Tool 的当前工作流程。 |
| `langgraph.json` | LangGraph / LangSmith 加载图的配置。 |
| `pyproject.toml` | Python 包配置。 |
| `requirements.txt` | 运行依赖。 |
| `alembic.ini`、`migrations/` | MySQL migration 配置和脚本。 |
| `api.py` | FastAPI Workflow API。 |
| `worker.py` | Redis Stream workflow worker。 |
| `demo.py` | 同步和异步命令行调试入口。 |
| `agents/graph.py` | LangGraph 固定入口，调用 workflow runtime。 |
| `agents/state.py` | LangGraph 公开输入输出状态。 |
| `agents/workflowagent/agent.py` | workflowagent，生成动态 workflow_plan。 |
| `Prompt/workflowagent.yaml` | workflowagent 系统提示词。 |
| `workflow/` | 执行器、计划校验、上下文、Tool 分发、业务 Agent、写入校验。 |
| `storage/` | SQLAlchemy 模型、Repository、MySQL/内存存储工厂。 |
| `runtime/` | Redis Stream/内存运行态工厂。 |
| `Tool/tool_ReadFeishuBitableSchema.py` | 飞书字段定义读取 Tool。 |
| `Tool/tool_ReadFeishuBitable.py` | 飞书记录读取 Tool。 |
| `Tool/tool_CreateFeishuBitableRecord.py` | 飞书新增记录 Tool。 |
| `Tool/tool_UpdateFeishuBitableRecord.py` | 飞书更新记录 Tool。 |
| `Tool/tool_DeleteFeishuBitableRecord.py` | 飞书删除记录 Tool。 |
| `Tool/write_support.py` | 写入类 Tool 共用字段校验和值转换逻辑。 |
| `Tool/field_context.py` | 读取真实或 mock 表字段上下文，接入 TTL 字段缓存。 |
| `Tool/feishu_client.py` | 飞书 OpenAPI HTTP 客户端。 |
| `Tool/mock_repository.py` | mock 多维表格 CRUD 逻辑。 |
| `agents/shared/config.py` | 飞书、OpenAI、MySQL、Redis、workflow 环境配置。 |
