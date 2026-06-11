"""业务 Agent Runner，负责无状态步骤转换。"""

from __future__ import annotations

import json
from typing import Any

try:
    from ..Tool.write_support import build_write_request
    from ..agents.shared.config import load_config
    from ..agents.shared.json_utils import dumps_json
    from ..agents.shared.time_utils import now_iso
    from ..agents.workflowagent.agent import CREATE_TOOL, DELETE_TOOL, UPDATE_TOOL
    from ..storage.factory import get_workflow_repository
    from .content import load_json_object
except ImportError:
    from Tool.write_support import build_write_request
    from agents.shared.config import load_config
    from agents.shared.json_utils import dumps_json
    from agents.shared.time_utils import now_iso
    from agents.workflowagent.agent import CREATE_TOOL, DELETE_TOOL, UPDATE_TOOL
    from storage.factory import get_workflow_repository
    from workflow.content import load_json_object


PARSE_FEISHU_RECORD_PROMPT = "parse_feishu_record.v1"


# 这个函数运行当前步骤指定的业务 Agent；第一版只实现飞书写入 payload 解析。
def run_business_agent(context: dict[str, Any]) -> dict[str, Any]:
    prompt_ref = str(context.get("step", {}).get("prompt_ref") or "")
    if prompt_ref == PARSE_FEISHU_RECORD_PROMPT:
        return _parse_feishu_record(context)
    raise ValueError(f"当前业务 Agent 暂不支持该 prompt_ref：{prompt_ref}")


# 这个函数把用户输入转换成飞书写入类 Tool 可使用的结构化 payload。
def _parse_feishu_record(context: dict[str, Any]) -> dict[str, Any]:
    config = load_config()
    original_input = str(context.get("original_input") or "")
    table_schema = context.get("artifacts", {}).get("feishu.table_schema", {}).get("data_json", {})
    table_fields = table_schema.get("table_fields") or {}
    intent = str(context.get("plan", {}).get("intent") or "")
    operation, tool_name, request_key = _operation_mapping(intent)
    if config.workflowagent_use_llm:
        write_request = _parse_feishu_record_with_llm(
            context,
            original_input,
            operation,
            request_key,
            table_fields,
            config,
        )
        source = "llm"
    else:
        write_request = build_write_request(operation, original_input, config, table_fields)
        source = "rule"
    tool_input_payload = {
        "original_input": original_input,
        request_key: write_request,
    }
    data_json = {
        "tool_name": tool_name,
        "operation": operation,
        "request_key": request_key,
        "tool_input_payload": tool_input_payload,
        "table_fields": table_fields,
        "source": source,
    }
    return {
        "content_text": json.dumps(data_json, ensure_ascii=False, default=str),
        "data_json": data_json,
        "schema_json": {"request_key": request_key, "tool_name": tool_name, "source": source},
    }


# 这个函数在 LLM 模式下把用户输入解析为飞书写入请求，失败时直接暴露错误。
def _parse_feishu_record_with_llm(
    context: dict[str, Any],
    original_input: str,
    operation: str,
    request_key: str,
    table_fields: dict[str, Any],
    config: Any,
) -> dict[str, Any]:
    if not config.openai_api_key:
        raise RuntimeError("THIRD_WORKFLOWAGENT_USE_LLM=1 但 OPENAI_API_KEY 未配置，无法运行 business_agent。")
    prompt_config = _load_business_prompt(PARSE_FEISHU_RECORD_PROMPT, context)
    prompt_text = str(prompt_config.get("prompt_text") or "").strip()
    if not prompt_text:
        raise RuntimeError(f"业务 Agent 提示词为空：{PARSE_FEISHU_RECORD_PROMPT}")
    output_schema = prompt_config.get("output_schema_json") or _default_output_schema()
    model_prompt = _build_llm_prompt(prompt_text, original_input, operation, request_key, table_fields, output_schema)
    response_text = _invoke_business_agent_model(model_prompt, config)
    payload = load_json_object(response_text)
    if not isinstance(payload, dict):
        raise ValueError("business_agent LLM 输出不是合法 JSON 对象。")
    write_request = payload.get(request_key)
    if operation == "create_record" and not isinstance(write_request, dict):
        records = payload.get("create_requests") or payload.get("records")
        if isinstance(records, list):
            write_request = {"records": records}
    if not isinstance(write_request, dict):
        raise ValueError(f"business_agent LLM 输出缺少 {request_key} 对象。")
    write_request["operation"] = operation
    write_request["service"] = "feishu_bitable"
    return write_request


# 这个函数只从 prompt_registry 读取提示词，运行时不读取文件兜底。
def _load_business_prompt(prompt_key: str, context: dict[str, Any]) -> dict[str, Any]:
    repository = context.get("repository")
    if repository is None or not hasattr(repository, "get_prompt"):
        repository = get_workflow_repository()
    prompt = repository.get_prompt(prompt_key)
    if not prompt:
        raise RuntimeError(f"数据库 prompt_registry 缺少启用提示词：{prompt_key}")
    return prompt


# 这个函数把提示词、字段上下文和输出 schema 组装成模型输入。
def _build_llm_prompt(
    prompt_text: str,
    original_input: str,
    operation: str,
    request_key: str,
    table_fields: dict[str, Any],
    output_schema: dict[str, Any],
) -> str:
    current_datetime = now_iso()
    context_payload = {
        "original_input": original_input,
        "current_datetime": current_datetime,
        "current_date": current_datetime.split("T", 1)[0],
        "operation": operation,
        "request_key": request_key,
        "table_fields": table_fields,
        "output_schema_json": output_schema,
    }
    return f"{prompt_text}\n\n当前上下文 JSON：\n{dumps_json(context_payload)}"


# 这个函数统一调用 business_agent 使用的 OpenAI 模型，便于测试替换。
def _invoke_business_agent_model(prompt: str, config: Any) -> str:
    try:
        from langchain_openai import ChatOpenAI
    except ImportError as exc:
        raise RuntimeError("缺少 langchain_openai 依赖，无法运行 business_agent LLM。") from exc
    try:
        response = ChatOpenAI(model=config.workflowagent_model, temperature=0, api_key=config.openai_api_key).invoke(prompt)
    except Exception as exc:
        raise RuntimeError(f"business_agent LLM 调用失败：{exc}") from exc
    return str(getattr(response, "content", ""))


# 这个函数定义 LLM 输出结构，提示词文件或数据库没有 schema 时使用。
def _default_output_schema() -> dict[str, Any]:
    request_shape = {
        "operation": "create_record | update_record | delete_record",
        "service": "feishu_bitable",
        "record_id": "可选；更新或删除时如用户明确提供则填写",
        "fields": "对象；新增/更新时只包含当前飞书字段名",
        "records": "可选；create_record 多条新增时使用，数组元素为包含 fields 的对象",
        "lookup": {
            "filter": {
                "conjunction": "and",
                "conditions": [{"field_name": "真实飞书字段名", "operator": "is", "value": "字段值"}],
            }
        },
    }
    return {
        "type": "object",
        "one_of_required_keys": ["create_request", "update_request", "delete_request"],
        "properties": {
            "create_request": request_shape,
            "update_request": request_shape,
            "delete_request": request_shape,
        },
    }


# 这个函数根据计划意图映射写入 Tool 和请求字段名。
def _operation_mapping(intent: str) -> tuple[str, str, str]:
    if intent == "delete_feishu_record":
        return "delete_record", DELETE_TOOL, "delete_request"
    if intent == "update_feishu_record":
        return "update_record", UPDATE_TOOL, "update_request"
    return "create_record", CREATE_TOOL, "create_request"
