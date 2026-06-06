# third 模块目录表

## 阅读顺序

1. `README.md`：先看模块目标、运行方式和环境变量。
2. `docs/总架构图.md`：再看第三方服务模块在总流程里的位置。
3. `agents/graph.py`：理解 LangGraph 如何串联 Router Agent 和 Read Agent。
4. `agents/router/agent.py`、`agents/read/agent.py`：分别看路由和读取实现。
5. `agents/shared/`、`agents/read/feishu_client.py`：最后看配置、字段和飞书真实接口。

## 目录表

| 路径 | 用途 |
| --- | --- |
| `README.md` | 模块说明、配置项、运行方式。 |
| `codex.md` | 当前目录表，方便快速定位文件。 |
| `docs/总架构图.md` | 第三方服务模块的整体架构图。 |
| `langgraph.json` | LangGraph / LangSmith 加载图的配置。 |
| `pyproject.toml` | 本模块作为 Python 包安装时的项目配置。 |
| `requirements.txt` | 运行 LangGraph 和 OpenAI 路由所需依赖。 |
| `demo.py` | 命令行测试入口。 |
| `agents/graph.py` | LangGraph 主图，负责 Router -> Read 的节点编排。 |
| `agents/state.py` | LangGraph 节点间传递的状态结构。 |
| `agents/router/agent.py` | Router Agent，将自然语言整理成读取请求。 |
| `agents/read/agent.py` | Read Agent，选择真实飞书读取或 mock 读取，并整理输出。 |
| `agents/read/feishu_client.py` | 真实飞书多维表格读取客户端。 |
| `agents/read/mock_repository.py` | mock 多维表格读取逻辑。 |
| `agents/shared/config.py` | 飞书、OpenAI、LangSmith 相关环境配置读取。 |
| `agents/shared/feishu_schema.py` | 飞书读取字段 schema 和字段别名。 |
| `agents/shared/mock_feishu.py` | mock 飞书记录数据。 |
| `agents/shared/time_utils.py` | 通用时间工具。 |

