# 第三方服务模块

当前实现范围：

- `agents/router/`：Router Agent，将自然语言整理成飞书读取请求。
- `agents/read/field_context.py`：字段上下文读取，先读取当前飞书表真实字段，再交给 Router。
- `agents/read/`：Read Agent，按读取请求查询真实飞书多维表格；配置不完整时使用 mock 数据。
- `agents/shared/`：配置、飞书字段 schema、mock 数据和通用工具。
- `agents/graph.py`：LangGraph 主图，串联 Router Agent 和 Read Agent。

## 你需要收集的信息

配置写在 `third/.env`，不要写在 `.env.example`。`.env.example` 只是模板。

真实读取飞书多维表格时需要：

- `THIRD_FEISHU_APP_ID`：飞书应用 app id。
- `THIRD_FEISHU_APP_SECRET`：飞书应用 app secret。
- `THIRD_FEISHU_APP_TOKEN`：多维表格 app token。
- `THIRD_FEISHU_TABLE_ID`：多维表格 table id。
- `THIRD_FEISHU_VIEW_ID`：可选，指定视图读取。
- `THIRD_FEISHU_USER_ID_TYPE`：可选，默认 `open_id`。
- `THIRD_FEISHU_FIELD_NAME_MAP`：可选兜底配置。正常流程会自动读取真实字段，不要求你本地确定字段。

如果你已经有可用的 `tenant_access_token`，也可以直接填 `THIRD_FEISHU_TENANT_ACCESS_TOKEN`，此时可以不填 `APP_ID/APP_SECRET`。

OpenAI 相关：

- `OPENAI_API_KEY`：用于 Router Agent 的 LLM 字段整理，不负责读取飞书。
- `THIRD_AGENT_USE_LLM=1`：启用 LLM 路由；不启用时使用规则路由。
- `THIRD_ROUTER_MODEL`：默认 `gpt-4o-mini`。

最小真实读取配置示例：

```env
THIRD_FEISHU_USE_REAL=1
THIRD_FEISHU_APP_ID=cli_xxx
THIRD_FEISHU_APP_SECRET=xxx
THIRD_FEISHU_APP_TOKEN=app_xxx
THIRD_FEISHU_TABLE_ID=tbl_xxx

THIRD_AGENT_USE_LLM=1
OPENAI_API_KEY=sk-xxx
```

## 运行方式

安装依赖：

```bash
pip install -r third/requirements.txt
```

mock 模式验证：

```bash
python -m third.demo "查询状态为进行中的记录，只返回标题、状态、截止时间"
```

真实飞书读取：

```bash
copy third\.env.example third\.env
# 然后编辑 third\.env，填入飞书和 OpenAI 配置
python -m third.demo "查询状态为进行中的记录，只返回标题、状态、截止时间"
```

LangGraph / LangSmith 调试：

```bash
cd third
langgraph dev
```

输入状态示例：

```json
{
  "input": "查询状态为进行中的记录，只返回标题、状态、截止时间"
}
```

输出状态中的 `table_fields` 可检查系统读取到的真实表字段，`route` 可检查 Router Agent 整理出的字段，`read_request` 可检查传给 Read Agent 的飞书读取请求，`read_result` 可检查真实或 mock 读取结果。

## 常见报错理解

- `HTTP 400` + `field validation failed`：请求字段格式不对，还没有真正查表。优先看 `field_violations`，例如 `operator=equals` 表示过滤操作符不符合飞书枚举。
- `FieldNameNotFound`：请求里使用了真实表不存在的字段名。优先检查 `read_result.warnings` 里的真实字段列表，或配置 `THIRD_FEISHU_FIELD_NAME_MAP`。
- `HTTP 401` 或 token 相关错误：飞书应用凭证、`tenant_access_token` 或鉴权头有问题。
- `HTTP 403` 或权限相关错误：应用没有多维表格读取权限，或者目标表格没有授权给该应用。
- `HTTP 404`：通常是 `app_token`、`table_id`、`record_id` 不对。
- 请求成功但 `record_count=0`：这才通常表示表里没有数据，或者过滤条件没有匹配到数据。
