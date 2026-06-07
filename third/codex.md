# third 模块目录表

## 阅读顺序

1. `README.md`：先看模块目标、运行方式和环境变量。
2. `docs/router-read00.md`：查看当前 finagent 到 Tool 的输入输出流程。
3. `agents/graph.py`：理解 LangGraph 如何串联 finagent 和工具。
4. `agents/finagent/agent.py`、`Prompt/finagent.yaml`：查看 Agent 决策逻辑和提示词。
5. `Tool/tool_ReadFeishuBitable.py`：查看读取工具的入口和请求整理逻辑。
6. `Tool/feishu_client.py`、`Tool/field_context.py`：查看真实飞书接口和字段上下文读取。
7. `agents/shared/`：最后看配置、字段 schema、mock 数据和通用工具。

## 目录表

| 路径 | 用途 |
| --- | --- |
| `README.md` | 模块说明、配置项、运行方式。 |
| `codex.md` | 当前目录表，方便快速定位文件。 |
| `docs/总架构图.md` | 第三方服务模块的整体架构图。 |
| `docs/router-read00.md` | finagent 到 Tool 的工作流程说明。 |
| `langgraph.json` | LangGraph / LangSmith 加载图的配置。 |
| `pyproject.toml` | 本模块作为 Python 包安装时的项目配置。 |
| `requirements.txt` | 运行 LangGraph 和 OpenAI finagent 所需依赖。 |
| `demo.py` | 命令行测试入口，输入会包装为 `content[0].text`。 |
| `agents/graph.py` | LangGraph 主图，负责 `finagent -> tool_ReadFeishuBitable -> finagent` 编排。 |
| `agents/state.py` | LangGraph 节点间传递的 `content` 状态结构。 |
| `agents/finagent/agent.py` | finagent，根据 `content[0].text` 决定调用工具或输出最终答案。 |
| `Prompt/finagent.yaml` | finagent 系统提示词。 |
| `Tool/tool_ReadFeishuBitable.py` | 飞书多维表格读取工具入口。 |
| `Tool/field_context.py` | 读取真实或 mock 表字段上下文。 |
| `Tool/feishu_client.py` | 真实飞书多维表格 HTTP 客户端。 |
| `Tool/mock_repository.py` | mock 多维表格读取逻辑。 |
| `agents/shared/config.py` | 飞书、OpenAI、LangSmith 相关环境配置读取。 |
| `agents/shared/feishu_schema.py` | 飞书读取字段 schema 和字段别名。 |
| `agents/shared/mock_feishu.py` | mock 飞书记录数据。 |
| `agents/shared/time_utils.py` | 通用时间工具。 |

