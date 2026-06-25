"""业务 Agent Runner，负责无状态步骤转换。"""

from __future__ import annotations

import json
import re
from copy import deepcopy
from typing import Any

try:
    from ..Tool.write_support import build_write_request
    from ..agents.shared.config import load_config
    from ..agents.shared.json_utils import dumps_json
    from ..agents.shared.openai_client import create_chat_openai
    from ..agents.shared.time_utils import now_iso
    from ..storage.factory import get_workflow_repository
    from .content import load_json_object
    from .registry import CREATE_TOOL, DELETE_TOOL, UPDATE_TOOL
except ImportError:
    from Tool.write_support import build_write_request
    from agents.shared.config import load_config
    from agents.shared.json_utils import dumps_json
    from agents.shared.openai_client import create_chat_openai
    from agents.shared.time_utils import now_iso
    from storage.factory import get_workflow_repository
    from workflow.content import load_json_object
    from workflow.registry import CREATE_TOOL, DELETE_TOOL, UPDATE_TOOL


PARSE_FEISHU_RECORD_PROMPT = "parse_feishu_record.v1"
PARSE_RECORD_DRAFT_PROMPT = "parse_record_draft.v1"
SEARCH_FEISHU_RECORD_PROMPT = "search_feishu_record.v1"
PARSE_FEISHU_SCHEMA_CHANGE_PROMPT = "parse_feishu_schema_change.v1"

REPORT_SCHEMA_FIELDS = [
    {"field_name": "记录类型", "field_type": "single_select", "property": {"options": ["每日内容", "周报", "月报"]}, "reason": "用于区分记录粒度"},
    {"field_name": "日期", "field_type": "date", "property": {}, "reason": "用于记录每日内容日期"},
    {"field_name": "周期开始", "field_type": "date", "property": {}, "reason": "用于记录周报或月报周期开始时间"},
    {"field_name": "周期结束", "field_type": "date", "property": {}, "reason": "用于记录周报或月报周期结束时间"},
    {"field_name": "事项名称", "field_type": "text", "property": {}, "reason": "用于保存记录标题或事项名称"},
    {"field_name": "总结", "field_type": "text", "property": {}, "reason": "用于保存每日内容、周报或月报正文摘要"},
    {"field_name": "下阶段计划", "field_type": "text", "property": {}, "reason": "用于保存后续计划"},
]


# 这个函数运行当前步骤指定的业务 Agent；第一版只实现飞书写入 payload 解析。
def run_business_agent(context: dict[str, Any]) -> dict[str, Any]:
    prompt_ref = str(context.get("step", {}).get("prompt_ref") or "")
    if prompt_ref == PARSE_RECORD_DRAFT_PROMPT:
        return _parse_record_draft(context)
    if prompt_ref == PARSE_FEISHU_RECORD_PROMPT:
        return _parse_feishu_record(context)
    if prompt_ref == SEARCH_FEISHU_RECORD_PROMPT:
        return _search_feishu_record(context)
    if prompt_ref == PARSE_FEISHU_SCHEMA_CHANGE_PROMPT:
        return _parse_feishu_schema_change(context)
    raise ValueError(f"当前业务 Agent 暂不支持该 prompt_ref：{prompt_ref}")


# 这个函数把记录对话上下文整理成前端可展示的草稿结构。
def _parse_record_draft(context: dict[str, Any]) -> dict[str, Any]:
    original_input = str(context.get("original_input") or "").strip()
    cleaned = _clean_record_draft_input(original_input)
    score = _rule_score(cleaned)
    tags = _rule_tags(cleaned)
    title = "今日自律记录"
    summary = _summary_from_text(cleaned)
    data_json = {
        "title": title,
        "recordDate": _extract_record_date(cleaned),
        "summary": summary,
        "score": score,
        "tags": tags,
        "suggestion": "明天可以继续关注执行节奏和精力变化。",
        "previewText": cleaned or "我整理了一版草稿，你可以继续补充今天的记录。",
        "draft": {
            "title": title,
            "recordDate": _extract_record_date(cleaned),
            "summary": summary,
            "score": score,
            "tags": tags,
            "suggestion": "明天可以继续关注执行节奏和精力变化。",
        },
        "source": "rule",
    }
    return {
        "content_text": dumps_json(data_json),
        "data_json": data_json,
        "schema_json": {"type": "record_draft", "source": "rule"},
    }


# 这个函数把用户输入转换成飞书写入类 Tool 可使用的结构化 payload。
def _parse_feishu_record(context: dict[str, Any]) -> dict[str, Any]:
    config = load_config()
    original_input = str(context.get("original_input") or "")
    table_fields = _table_fields_from_artifacts(context)
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
    tool_input_payload = _public_tool_input_payload({
        "original_input": original_input,
        request_key: write_request,
    })
    data_json = {
        "tool_name": tool_name,
        "operation": operation,
        "request_key": request_key,
        "tool_input_payload": tool_input_payload,
        "table_fields": table_fields,
        "source": source,
    }
    if operation in {"update_record", "delete_record"}:
        data_json["candidate_read_payload"] = _public_tool_input_payload(_candidate_read_payload(original_input, write_request))
    return {
        "content_text": json.dumps(data_json, ensure_ascii=False, default=str),
        "data_json": data_json,
        "schema_json": {"request_key": request_key, "tool_name": tool_name, "source": source},
    }


# 这个函数把用户输入转换成飞书字段变更请求。
def _parse_feishu_schema_change(context: dict[str, Any]) -> dict[str, Any]:
    config = load_config()
    original_input = str(context.get("original_input") or "")
    table_fields = _table_fields_from_artifacts(context)
    if config.workflowagent_use_llm:
        schema_change_request = _parse_schema_change_with_llm(context, original_input, table_fields, config)
        source = "llm"
    else:
        schema_change_request = _parse_schema_change_without_llm(original_input, table_fields)
        source = "rule"
    schema_change_request["operation"] = "change_fields"
    schema_change_request["service"] = "feishu_bitable"
    tool_input_payload = _public_tool_input_payload({
        "original_input": original_input,
        "schema_change_request": schema_change_request,
    })
    data_json = {
        "tool_name": "tool_ChangeFeishuBitableFields",
        "operation": "change_fields",
        "request_key": "schema_change_request",
        "tool_input_payload": tool_input_payload,
        "table_fields": table_fields,
        "source": source,
    }
    return {
        "content_text": json.dumps(data_json, ensure_ascii=False, default=str),
        "data_json": data_json,
        "schema_json": {"request_key": "schema_change_request", "tool_name": "tool_ChangeFeishuBitableFields", "source": source},
    }


def _parse_schema_change_with_llm(
    context: dict[str, Any],
    original_input: str,
    table_fields: dict[str, Any],
    config: Any,
) -> dict[str, Any]:
    if not config.openai_api_key:
        raise RuntimeError("THIRD_WORKFLOWAGENT_USE_LLM=1 但 OPENAI_API_KEY 未配置，无法运行 schema_agent。")
    prompt_config = _load_business_prompt(PARSE_FEISHU_SCHEMA_CHANGE_PROMPT, context)
    prompt_text = str(prompt_config.get("prompt_text") or "").strip()
    if not prompt_text:
        raise RuntimeError(f"业务 Agent 提示词为空：{PARSE_FEISHU_SCHEMA_CHANGE_PROMPT}")
    output_schema = prompt_config.get("output_schema_json") or _default_schema_change_output_schema()
    model_prompt = _build_schema_change_llm_prompt(prompt_text, original_input, table_fields, output_schema)
    response_text = _invoke_business_agent_model(model_prompt, config)
    payload = load_json_object(response_text)
    if not isinstance(payload, dict):
        raise ValueError("schema_agent LLM 输出不是合法 JSON 对象。")
    request = payload.get("schema_change_request")
    if not isinstance(request, dict):
        raise ValueError("schema_agent LLM 输出缺少 schema_change_request 对象。")
    return request


def _parse_schema_change_without_llm(original_input: str, table_fields: dict[str, Any]) -> dict[str, Any]:
    actions: list[dict[str, Any]] = []
    existing_names = set(str(name) for name in table_fields.get("field_names", []) if name)
    if _looks_like_report_schema_request(original_input):
        for field in REPORT_SCHEMA_FIELDS:
            if field["field_name"] in existing_names:
                continue
            actions.append({"action": "create_field", **field})
    actions.extend(_extract_rename_field_actions(original_input))
    actions.extend(_extract_delete_field_actions(original_input))
    actions.extend(_extract_create_field_actions(original_input, existing_names | {str(action.get("field_name")) for action in actions}))
    return {
        "operation": "change_fields",
        "service": "feishu_bitable",
        "actions": actions,
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


def _public_tool_input_payload(payload: dict[str, Any]) -> dict[str, Any]:
    cleaned = deepcopy(payload)
    _strip_sensitive_request_fields(cleaned)
    return cleaned


def _strip_sensitive_request_fields(value: Any) -> None:
    if isinstance(value, dict):
        for key in ("app_token", "table_fields", "tenant_access_token", "app_secret", "authorization"):
            value.pop(key, None)
        for item in value.values():
            _strip_sensitive_request_fields(item)
    elif isinstance(value, list):
        for item in value:
            _strip_sensitive_request_fields(item)


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


def _table_fields_from_artifacts(context: dict[str, Any]) -> dict[str, Any]:
    artifacts = context.get("artifacts") or {}
    for artifact_key in ("feishu.table_schema_after", "feishu.table_schema"):
        table_schema = (artifacts.get(artifact_key) or {}).get("data_json") or {}
        table_fields = table_schema.get("table_fields")
        if isinstance(table_fields, dict):
            return table_fields
    return {}


def _build_schema_change_llm_prompt(
    prompt_text: str,
    original_input: str,
    table_fields: dict[str, Any],
    output_schema: dict[str, Any],
) -> str:
    current_datetime = now_iso()
    context_payload = {
        "original_input": original_input,
        "current_datetime": current_datetime,
        "current_date": current_datetime.split("T", 1)[0],
        "table_fields": table_fields,
        "default_report_schema_fields": REPORT_SCHEMA_FIELDS,
        "output_schema_json": output_schema,
    }
    return f"{prompt_text}\n\n当前上下文 JSON：\n{dumps_json(context_payload)}"


def _default_schema_change_output_schema() -> dict[str, Any]:
    return {
        "type": "object",
        "required": ["schema_change_request"],
        "properties": {
            "schema_change_request": {
                "operation": "change_fields",
                "service": "feishu_bitable",
                "actions": [
                    {
                        "action": "create_field | update_field | delete_field",
                        "field_name": "目标字段名",
                        "source_field_name": "更新或删除时的原字段名",
                        "field_type": "text | number | single_select | multi_select | date | checkbox | phone | url",
                        "property": {"options": ["选项A", "选项B"]},
                        "reason": "字段变更理由",
                    }
                ],
            }
        },
    }


def _looks_like_report_schema_request(original_input: str) -> bool:
    has_report = any(keyword in original_input for keyword in ("每日", "日记", "日报", "周报", "月报", "每周", "每月"))
    has_schema = any(keyword in original_input for keyword in ("字段", "列", "表结构", "结构", "表"))
    return has_report and has_schema


def _extract_create_field_actions(original_input: str, existing_names: set[str]) -> list[dict[str, Any]]:
    actions: list[dict[str, Any]] = []
    for match in re.finditer(r"(?:新增|添加|创建)(?:一个|一列)?(?:字段|列)\s*(?:叫|为|名为|是|:|：)?\s*([^，。；;\n]+)", original_input):
        field_name = _clean_schema_field_name(match.group(1))
        if not field_name or field_name in existing_names:
            continue
        field_type = _infer_schema_field_type(original_input, field_name)
        property_config = _infer_schema_field_property(original_input, field_type)
        actions.append(
            {
                "action": "create_field",
                "field_name": field_name,
                "field_type": field_type,
                "property": property_config,
                "reason": "用户要求新增字段",
            }
        )
        existing_names.add(field_name)
    return actions


def _extract_rename_field_actions(original_input: str) -> list[dict[str, Any]]:
    actions: list[dict[str, Any]] = []
    for match in re.finditer(r"(?:把)?字段\s*([^，。；;\n]+?)\s*(?:重命名为|改名为|改成|改为)\s*([^，。；;\n]+)", original_input):
        source = _clean_schema_field_name(match.group(1))
        target = _clean_schema_field_name(match.group(2))
        if source and target:
            actions.append(
                {
                    "action": "update_field",
                    "source_field_name": source,
                    "field_name": target,
                    "reason": "用户要求重命名字段",
                }
            )
    return actions


def _extract_delete_field_actions(original_input: str) -> list[dict[str, Any]]:
    actions: list[dict[str, Any]] = []
    for match in re.finditer(r"(?:删除|移除|清理)(?:一个|一列)?(?:字段|列)\s*(?:叫|为|名为|是|:|：)?\s*([^，。；;\n]+)", original_input):
        field_name = _clean_schema_field_name(match.group(1))
        if field_name:
            actions.append(
                {
                    "action": "delete_field",
                    "field_name": field_name,
                    "reason": "用户明确要求删除字段",
                }
            )
    return actions


def _clean_schema_field_name(value: str) -> str:
    cleaned = value.strip(" \t\r\n，。；;")
    cleaned = re.sub(r"(字段|这一列|这个列|这一字段|这个字段)$", "", cleaned).strip()
    for separator in ("，", "。", "；", ";", "并", "然后"):
        if separator in cleaned:
            cleaned = cleaned.split(separator, 1)[0].strip()
    return cleaned


def _infer_schema_field_type(original_input: str, field_name: str) -> str:
    around_text = f"{field_name} {original_input}"
    if any(keyword in around_text for keyword in ("单选", "类型", "状态", "评级", "优先级")):
        return "single_select"
    if any(keyword in around_text for keyword in ("多选", "标签")):
        return "multi_select"
    if any(keyword in around_text for keyword in ("日期", "时间", "周期")):
        return "date"
    if any(keyword in around_text for keyword in ("数字", "数量", "用时", "金额", "分数")):
        return "number"
    if any(keyword in around_text for keyword in ("是否", "复选", "完成")):
        return "checkbox"
    if "链接" in around_text or "URL" in around_text.upper():
        return "url"
    if "电话" in around_text or "手机" in around_text:
        return "phone"
    return "text"


def _infer_schema_field_property(original_input: str, field_type: str) -> dict[str, Any]:
    if field_type not in {"single_select", "multi_select"}:
        return {}
    option_match = re.search(r"选项(?:为|是|包括|包含|:|：)?\s*([^。；;\n]+)", original_input)
    if not option_match:
        return {"options": ["待定"]}
    options = [item.strip(" \t\r\n，。；;") for item in re.split(r"[、,，/]\s*", option_match.group(1)) if item.strip()]
    return {"options": options or ["待定"]}


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
        response = create_chat_openai(config, config.workflowagent_model, temperature=0).invoke(prompt)
    except ImportError as exc:
        raise RuntimeError("缺少 langchain_openai 依赖，无法运行 business_agent LLM。") from exc
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


# 这个函数清理 SpringBoot 注入的草稿生成前缀，只保留用户记录上下文。
def _clean_record_draft_input(text: str) -> str:
    cleaned = re.sub(r"^生成记录草稿[:：]\s*", "", text.strip())
    cleaned = re.sub(r"当前记录会话上下文[:：]\s*", "", cleaned)
    return cleaned.strip()


# 这个函数根据记录内容生成稳定的 MVP 评分。
def _rule_score(text: str) -> int:
    score = 80
    positive_keywords = ("完成", "坚持", "按时", "阅读", "拉伸", "复盘", "整理", "计划")
    difficult_keywords = ("累", "疲惫", "困难", "阻力", "失败")
    score += min(15, sum(3 for keyword in positive_keywords if keyword in text))
    score -= min(10, sum(2 for keyword in difficult_keywords if keyword in text))
    return max(60, min(score, 98))


# 这个函数从记录内容提取展示标签。
def _rule_tags(text: str) -> list[str]:
    candidates = [
        ("阅读", "阅读"),
        ("拉伸", "运动"),
        ("早餐", "作息"),
        ("按时", "作息"),
        ("坚持", "坚持"),
        ("复盘", "复盘"),
        ("计划", "计划"),
    ]
    tags: list[str] = []
    for keyword, tag in candidates:
        if keyword in text and tag not in tags:
            tags.append(tag)
    return tags or ["记录"]


# 这个函数生成最近记录和草稿卡片的摘要。
def _summary_from_text(text: str) -> str:
    if not text:
        return "记录内容待补充。"
    normalized = re.sub(r"\s+", " ", text).strip()
    return normalized[:80] + ("..." if len(normalized) > 80 else "")


# 这个函数从文本里提取 yyyy-MM-dd 日期，未提供时由业务后端覆盖。
def _extract_record_date(text: str) -> str:
    match = re.search(r"\d{4}-\d{2}-\d{2}", text)
    return match.group(0) if match else ""
