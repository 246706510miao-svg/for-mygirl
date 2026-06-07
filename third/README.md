# 第三方服务模块

当前实现范围：

- `agents/finagent/`：唯一 Agent，接收 `content[0].text`，决定调用工具或生成最终答案。
- `Tool/tool_ReadFeishuBitable.py`：飞书多维表格读取工具，负责字段读取、请求整理、真实飞书或 mock 查询。
- `Tool/feishu_client.py`：真实飞书多维表格 HTTP 客户端。
- `Tool/field_context.py`：读取当前表字段上下文，优先使用真实飞书字段。
- `Tool/mock_repository.py`：无真实凭证时使用的 mock 表读取逻辑。
- `Prompt/finagent.yaml`：finagent 的系统提示词。
- `agents/shared/`：配置、飞书字段 schema、mock 数据和通用工具。
- `agents/graph.py`：LangGraph 主图，串联 `finagent -> tool_ReadFeishuBitable -> finagent`。

## 你需要收集的信息

配置写在 `third/.env`，不要写在 `.env.example`。`.env.example` 只是模板。

真实读取飞书多维表格时需要：

- `THIRD_FEISHU_APP_ID`：飞书应用 app id。
- `THIRD_FEISHU_APP_SECRET`：飞书应用 app secret。
- `THIRD_FEISHU_APP_TOKEN`：多维表格 app token。
- `THIRD_FEISHU_TABLE_ID`：多维表格 table id。
- `THIRD_FEISHU_VIEW_ID`：可选，指定视图读取。
- `THIRD_FEISHU_USER_ID_TYPE`：可选，默认 `open_id`。
- `THIRD_FEISHU_FIELD_NAME_MAP`：可选兜底配置。正常流程会自动读取真实字段。

如果你已经有可用的 `tenant_access_token`，也可以直接填 `THIRD_FEISHU_TENANT_ACCESS_TOKEN`，此时可以不填 `APP_ID/APP_SECRET`。

OpenAI 相关：

- `OPENAI_API_KEY`：用于 finagent 判断工具调用和总结结果。
- `THIRD_FINAGENT_USE_LLM=1`：启用 strict LLM 模式；LLM 失败或输出格式错误时直接报错，不使用规则兜底。
- `THIRD_FINAGENT_MODEL`：默认 `gpt-4o-mini`。

最小真实读取配置示例：

```env
THIRD_FEISHU_USE_REAL=1
THIRD_FEISHU_APP_ID=cli_xxx
THIRD_FEISHU_APP_SECRET=xxx
THIRD_FEISHU_APP_TOKEN=app_xxx
THIRD_FEISHU_TABLE_ID=tbl_xxx

THIRD_FINAGENT_USE_LLM=1
THIRD_FINAGENT_MODEL=gpt-4o-mini
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

strict LLM 模式验证：

```bash
# third/.env 中配置 THIRD_FINAGENT_USE_LLM=1 和 OPENAI_API_KEY
python -m third.demo "我的飞书里现在有什么内容"
```

说明：`THIRD_FINAGENT_USE_LLM=1` 时，finagent 必须用 LLM 生成结构化 tool 调用，Tool 必须收到包含 `read_request` 的 JSON；如果模型输出自然语言或非法 JSON，系统会返回 strict mode 错误。

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
  "content": [
    {
      "text": "查询状态为进行中的记录，只返回标题、状态、截止时间"
    }
  ]
}
```

最终输出仍然读取：

```json
{
  "content": [
    {
      "text": "finagent 总结后的答案"
    }
  ]
}
```

## 常见报错理解

- `LLM strict mode 错误`：`THIRD_FINAGENT_USE_LLM=1` 时 LLM 没有成功返回合法 JSON，或 `tool_call/answer` 结构不符合要求；系统不会使用规则兜底。
- `strict_input_validation`：Tool 在 strict LLM 模式下没有收到包含 `read_request` 的 JSON，通常是 finagent prompt 或模型输出格式不对。
- `HTTP 400` + `field validation failed`：请求字段格式不对。优先看 `field_violations`，例如 `operator=equals` 表示过滤操作符不符合飞书枚举。
- `FieldNameNotFound`：请求里使用了真实表不存在的字段名。工具会先读取真实字段并尽量避免传错字段。
- `HTTP 401` 或 token 相关错误：飞书应用凭证、`tenant_access_token` 或鉴权头有问题。
- `HTTP 403` 或权限相关错误：应用没有多维表格读取权限，或者目标表格没有授权给该应用。
- `HTTP 404`：通常是 `app_token`、`table_id`、`record_id` 不对。
- 请求成功但查询不到记录：通常表示表里没有数据，或者过滤条件没有匹配到数据。
