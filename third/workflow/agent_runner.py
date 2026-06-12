"""业务 Agent Runner，负责无状态步骤转换。"""

from __future__ import annotations

import json
from copy import deepcopy
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
SEARCH_FEISHU_RECORD_PROMPT = "search_feishu_record.v1"


# 这个函数运行当前步骤指定的业务 Agent；第一版只实现飞书写入 payload 解析。
def run_business_agent(context: dict[str, Any]) -> dict[str, Any]:
    prompt_ref = str(context.get("step", {}).get("prompt_ref") or "")
    if prompt_ref == PARSE_FEISHU_RECORD_PROMPT:
        return _parse_feishu_record(context)
    if prompt_ref == SEARCH_FEISHU_RECORD_PROMPT:
        return _search_feishu_record(context)
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
    if operation in {"update_record", "delete_record"}:
        data_json["candidate_read_payload"] = _candidate_read_payload(original_input, write_request)
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


# 这个函数根据更新/删除候选 payload 构造候选读取请求，供 search_agent 做语义匹配。
def _candidate_read_payload(original_input: str, write_request: dict[str, Any]) -> dict[str, Any]:
    record_id = write_request.get("record_id")
    lookup = write_request.get("lookup") if isinstance(write_request.get("lookup"), dict) else {}
    filter_config = lookup.get("filter") if isinstance(lookup.get("filter"), dict) else {"conjunction": "and", "conditions": []}
    read_request = {
        "operation": "get_record" if record_id else "search_records",
        "service": "feishu_bitable",
        "record_id": record_id,
        "field_names": [],
        "filter": filter_config,
        "sort": [],
        "page_size": 50,
        "automatic_fields": True,
    }
    return {
        "original_input": original_input,
        "read_request": read_request,
    }


# 这个函数在更新/删除前从候选记录中匹配用户真正要操作的 record_id。
def _search_feishu_record(context: dict[str, Any]) -> dict[str, Any]:
    config = load_config()
    original_input = str(context.get("original_input") or "")
    parsed_payload = _find_parsed_write_payload(context)
    candidate_result = (context.get("artifacts", {}).get("feishu.candidate_records") or {}).get("data_json") or {}
    records = candidate_result.get("records") or []
    if not isinstance(records, list) or not records:
        raise ValueError("search_agent 没有可匹配的候选记录。")
    table_fields = parsed_payload.get("table_fields") or candidate_result.get("table_fields") or {}
    operation = str(parsed_payload.get("operation") or "")
    request_key = str(parsed_payload.get("request_key") or "")
    parsed_write_payload = deepcopy((parsed_payload.get("tool_input_payload") or {}).get(request_key) or {})

    if config.workflowagent_use_llm:
        matched_record = _search_feishu_record_with_llm(
            context,
            original_input,
            operation,
            request_key,
            parsed_write_payload,
            records,
            table_fields,
            config,
        )
        source = "llm"
    else:
        matched_record = _search_feishu_record_without_llm(parsed_write_payload, records)
        source = "rule"

    _ensure_matched_record(matched_record, records)
    data_json = {
        "operation": operation,
        "request_key": request_key,
        "matched_record": matched_record,
        "candidate_record_count": len(records),
        "source": source,
    }
    return {
        "content_text": dumps_json(data_json),
        "data_json": data_json,
        "schema_json": {"type": "feishu_record_match", "source": source},
    }


def _search_feishu_record_with_llm(
    context: dict[str, Any],
    original_input: str,
    operation: str,
    request_key: str,
    parsed_write_payload: dict[str, Any],
    candidate_records: list[dict[str, Any]],
    table_fields: dict[str, Any],
    config: Any,
) -> dict[str, Any]:
    if not config.openai_api_key:
        raise RuntimeError("THIRD_WORKFLOWAGENT_USE_LLM=1 但 OPENAI_API_KEY 未配置，无法运行 search_agent。")
    prompt_config = _load_business_prompt(SEARCH_FEISHU_RECORD_PROMPT, context)
    prompt_text = str(prompt_config.get("prompt_text") or "").strip()
    if not prompt_text:
        raise RuntimeError(f"业务 Agent 提示词为空：{SEARCH_FEISHU_RECORD_PROMPT}")
    output_schema = prompt_config.get("output_schema_json") or _default_search_output_schema()
    model_prompt = _build_search_llm_prompt(
        prompt_text,
        original_input,
        operation,
        request_key,
        parsed_write_payload,
        candidate_records,
        table_fields,
        output_schema,
    )
    response_text = _invoke_business_agent_model(model_prompt, config)
    payload = load_json_object(response_text)
    if not isinstance(payload, dict):
        raise ValueError("search_agent LLM 输出不是合法 JSON 对象。")
    matched_record = payload.get("matched_record")
    if not isinstance(matched_record, dict):
        raise ValueError("search_agent LLM 输出缺少 matched_record 对象。")
    return matched_record


def _search_feishu_record_without_llm(parsed_write_payload: dict[str, Any], candidate_records: list[dict[str, Any]]) -> dict[str, Any]:
    requested_id = parsed_write_payload.get("record_id")
    if requested_id:
        for record in candidate_records:
            if str(record.get("record_id") or "") == str(requested_id):
                return _matched_record_from_candidate(record, 1.0, "high", "规则模式按用户提供的 record_id 匹配。", [])
    alternatives = [_candidate_summary(record) for record in candidate_records[1:6]]
    return _matched_record_from_candidate(
        candidate_records[0],
        0.3,
        "low",
        "规则模式无法语义匹配，默认选择第一条候选记录，请在确认前仔细核对。",
        alternatives,
    )


def _find_parsed_write_payload(context: dict[str, Any]) -> dict[str, Any]:
    artifacts = context.get("artifacts") or {}
    for artifact_key in ("feishu.update_payload", "feishu.delete_payload"):
        if artifact_key in artifacts:
            return artifacts[artifact_key].get("data_json") or {}
    raise ValueError("search_agent 缺少更新或删除 payload artifact。")


def _build_search_llm_prompt(
    prompt_text: str,
    original_input: str,
    operation: str,
    request_key: str,
    parsed_write_payload: dict[str, Any],
    candidate_records: list[dict[str, Any]],
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
        "parsed_write_payload": parsed_write_payload,
        "candidate_records": candidate_records,
        "table_fields": table_fields,
        "output_schema_json": output_schema,
    }
    return f"{prompt_text}\n\n当前上下文 JSON：\n{dumps_json(context_payload)}"


def _default_search_output_schema() -> dict[str, Any]:
    return {
        "type": "object",
        "required": ["matched_record"],
        "properties": {
            "matched_record": {
                "record_id": "必须来自 candidate_records 中的 record_id",
                "confidence": "0 到 1 的数字",
                "confidence_level": "high | medium | low",
                "reason": "匹配理由",
                "record_fields": "被选中记录的 fields",
                "alternative_records": "其他可能候选摘要数组",
            }
        },
    }


def _ensure_matched_record(matched_record: dict[str, Any], candidate_records: list[dict[str, Any]]) -> None:
    record_id = str(matched_record.get("record_id") or "").strip()
    if not record_id:
        raise ValueError("search_agent 未输出可用 record_id。")
    candidate_ids = {str(record.get("record_id") or "").strip() for record in candidate_records if record.get("record_id")}
    if record_id not in candidate_ids:
        raise ValueError(f"search_agent 输出的 record_id 不在候选记录中：{record_id}")
    if "confidence" not in matched_record:
        matched_record["confidence"] = 0
    if not matched_record.get("confidence_level"):
        matched_record["confidence_level"] = _confidence_level(matched_record.get("confidence"))
    matched_record.setdefault("reason", "")
    matched_record.setdefault("record_fields", {})
    matched_record.setdefault("alternative_records", [])


def _confidence_level(confidence: Any) -> str:
    try:
        value = float(confidence)
    except (TypeError, ValueError):
        return "low"
    if value >= 0.8:
        return "high"
    if value >= 0.5:
        return "medium"
    return "low"


def _matched_record_from_candidate(
    record: dict[str, Any],
    confidence: float,
    confidence_level: str,
    reason: str,
    alternatives: list[dict[str, Any]],
) -> dict[str, Any]:
    return {
        "record_id": str(record.get("record_id") or ""),
        "confidence": confidence,
        "confidence_level": confidence_level,
        "reason": reason,
        "record_fields": record.get("fields") or {},
        "alternative_records": alternatives,
    }


def _candidate_summary(record: dict[str, Any]) -> dict[str, Any]:
    return {
        "record_id": record.get("record_id"),
        "fields": record.get("fields") or {},
    }


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
