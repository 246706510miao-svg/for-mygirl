"""workflowagent：把自然语言请求规划成动态 workflow_plan。"""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

try:
    from ..shared.config import ThirdServiceConfig, load_config
    from ...workflow.content import load_json_object
except ImportError:
    from agents.shared.config import ThirdServiceConfig, load_config
    from workflow.content import load_json_object


# 这一段定义 workflow 当前允许调用的工具名称。
READ_SCHEMA_TOOL = "tool_ReadFeishuBitableSchema"
READ_TOOL = "tool_ReadFeishuBitable"
CREATE_TOOL = "tool_CreateFeishuBitableRecord"
UPDATE_TOOL = "tool_UpdateFeishuBitableRecord"
DELETE_TOOL = "tool_DeleteFeishuBitableRecord"
WRITE_TOOLS = {CREATE_TOOL, UPDATE_TOOL, DELETE_TOOL}
ALLOWED_TOOLS = {READ_SCHEMA_TOOL, READ_TOOL, CREATE_TOOL, UPDATE_TOOL, DELETE_TOOL}


# 这一段定义规则兜底意图关键词。
READ_KEYWORDS = ("查询", "读取", "搜索", "查找", "查", "列出", "获取", "看看", "看一下", "显示", "总结")
CREATE_KEYWORDS = ("新增", "添加", "创建", "写入", "保存", "记录一下", "记一下")
UPDATE_KEYWORDS = ("修改", "更新", "改成", "改为", "调整")
DELETE_KEYWORDS = ("删除", "移除", "清理")


# 这个函数是 workflowagent 的入口，优先使用 LLM，失败或未配置时使用规则计划。
def build_workflow_plan(input_text: str, config: ThirdServiceConfig | None = None) -> dict[str, Any]:
    resolved_config = config or load_config()
    if resolved_config.workflowagent_use_llm and resolved_config.openai_api_key:
        llm_plan = _try_llm_plan(input_text, resolved_config)
        if llm_plan:
            return llm_plan
    return _rule_based_plan(input_text)


# 这个函数尝试调用 OpenAI 生成 workflow_plan。
def _try_llm_plan(input_text: str, config: ThirdServiceConfig) -> dict[str, Any] | None:
    try:
        from langchain_openai import ChatOpenAI
    except ImportError:
        return None

    prompt = f"{_load_prompt()}\n\n用户 content[0].text：\n{input_text}"
    try:
        response = ChatOpenAI(model=config.workflowagent_model, temperature=0, api_key=config.openai_api_key).invoke(prompt)
    except Exception:
        return None
    payload = load_json_object(str(getattr(response, "content", "")))
    if isinstance(payload, dict) and payload.get("type") == "workflow_plan":
        return payload
    return None


# 这个函数读取 Prompt/workflowagent.yaml 中的系统提示词。
def _load_prompt() -> str:
    prompt_path = Path(__file__).resolve().parents[2] / "Prompt" / "workflowagent.yaml"
    if not prompt_path.exists():
        return "你是 workflowagent，只输出 workflow_plan JSON。"
    raw_text = prompt_path.read_text(encoding="utf-8")
    try:
        import yaml

        parsed = yaml.safe_load(raw_text)
        if isinstance(parsed, dict) and parsed.get("system"):
            return str(parsed["system"])
    except Exception:
        pass
    return raw_text


# 这个函数在没有 LLM 时生成稳定的规则 workflow_plan。
def _rule_based_plan(input_text: str) -> dict[str, Any]:
    intent = _detect_intent(input_text)
    if intent == "delete_feishu_record":
        return _write_plan(input_text, intent, "delete", DELETE_TOOL, "feishu.delete_payload")
    if intent == "update_feishu_record":
        return _write_plan(input_text, intent, "write", UPDATE_TOOL, "feishu.update_payload")
    if intent == "create_feishu_record":
        return _write_plan(input_text, intent, "write", CREATE_TOOL, "feishu.create_payload")
    return _read_plan(input_text)


# 这个函数根据关键词识别用户目标。
def _detect_intent(input_text: str) -> str:
    if any(keyword in input_text for keyword in DELETE_KEYWORDS):
        return "delete_feishu_record"
    if any(keyword in input_text for keyword in UPDATE_KEYWORDS):
        return "update_feishu_record"
    if any(keyword in input_text for keyword in CREATE_KEYWORDS):
        return "create_feishu_record"
    if any(keyword in input_text for keyword in READ_KEYWORDS):
        return "read_feishu_records"
    if "飞书" in input_text or "多维表格" in input_text or "表格" in input_text:
        return "read_feishu_records"
    return "read_feishu_records"


# 这个函数生成读取类 workflow_plan。
def _read_plan(input_text: str) -> dict[str, Any]:
    read_input = json.dumps(
        {
            "original_input": input_text,
            "read_request": {
                "operation": "search_records",
                "service": "feishu_bitable",
                "field_names": _extract_read_field_names(input_text),
                "filter": {"conjunction": "and", "conditions": _extract_read_conditions(input_text)},
                "sort": [],
                "page_size": 20,
                "automatic_fields": True,
            },
        },
        ensure_ascii=False,
    )
    return {
        "type": "workflow_plan",
        "version": "workflow.v1",
        "intent": "read_feishu_records",
        "risk_level": "read",
        "requires_confirmation": False,
        "original_input": input_text,
        "steps": [
            {
                "step_id": "step_read_records",
                "kind": "tool",
                "tool_name": READ_TOOL,
                "purpose": "读取飞书多维表格记录",
                "input": {"content": [{"text": read_input}]},
                "output": {"save_as": "feishu.records", "content_path": "content[0].text"},
                "validation": {"required": True},
            }
        ],
        "final": {"source": "feishu.records", "format": "answer"},
    }


# 这个函数从读取请求中抽取用户明确要求返回的字段。
def _extract_read_field_names(input_text: str) -> list[str]:
    match = re.search(r"(?:返回|输出|只看|只返回|字段)\s*[:：]?\s*([^，。；;]+(?:[、,，]\s*[^，。；;]+)*)", input_text)
    if not match:
        return []
    fields = [part.strip(" \t\r\n。；;") for part in re.split(r"[、,，\s]+", match.group(1)) if part.strip()]
    return _dedupe(fields)


# 这个函数从读取请求中抽取常见过滤条件，避免 strict 模式下丢失查询语义。
def _extract_read_conditions(input_text: str) -> list[dict[str, Any]]:
    conditions: list[dict[str, Any]] = []
    status_match = re.search(r"状态(?:为|是|=|：|:)?\s*([^\s，。；;]+)", input_text)
    if status_match:
        conditions.append({"field_name": "状态", "operator": "is", "value": _clean_condition_value(status_match.group(1))})
    else:
        for status in ("进行中", "已完成", "待开始", "未完成"):
            if status in input_text:
                conditions.append({"field_name": "状态", "operator": "is", "value": status})
                break

    priority_match = re.search(r"优先级(?:为|是|=|：|:)?\s*([高中低])", input_text)
    if priority_match:
        conditions.append({"field_name": "优先级", "operator": "is", "value": priority_match.group(1)})
    return conditions


# 这个函数清理过滤条件里常见的自然语言后缀。
def _clean_condition_value(value: str) -> str:
    cleaned = value.strip()
    for known in ("进行中", "已完成", "待开始", "未完成"):
        if known in cleaned:
            return known
    return re.sub(r"(的)?记录$", "", cleaned)


# 这个函数在保留顺序的同时去重。
def _dedupe(items: list[str]) -> list[str]:
    seen: set[str] = set()
    result: list[str] = []
    for item in items:
        if item not in seen:
            seen.add(item)
            result.append(item)
    return result


# 这个函数生成新增、更新、删除类 workflow_plan。
def _write_plan(input_text: str, intent: str, risk_level: str, write_tool: str, payload_key: str) -> dict[str, Any]:
    return {
        "type": "workflow_plan",
        "version": "workflow.v1",
        "intent": intent,
        "risk_level": risk_level,
        "requires_confirmation": True,
        "original_input": input_text,
        "steps": [
            {
                "step_id": "step_read_schema",
                "kind": "tool",
                "tool_name": READ_SCHEMA_TOOL,
                "purpose": "读取飞书字段定义",
                "input": {"content": [{"text": "读取当前飞书多维表格字段定义"}]},
                "output": {"save_as": "feishu.table_schema", "content_path": "content[0].text"},
                "validation": {"required": True},
            },
            {
                "step_id": "step_parse_payload",
                "kind": "agent",
                "agent_name": "business_agent",
                "prompt_ref": "parse_feishu_record.v1",
                "purpose": "把用户输入转换为飞书写入 payload",
                "input": {"from_session": ["feishu.table_schema"], "include_original_input": True},
                "output": {"save_as": payload_key},
                "validation": {"reject_unknown_fields": True, "must_match_feishu_schema": True},
            },
            {
                "step_id": "step_validate_payload",
                "kind": "validation",
                "purpose": "校验写入 payload 字段和定位条件",
                "input": {"from_session": ["feishu.table_schema", payload_key]},
                "output": {"save_as": "validation.write_payload"},
                "validation": {"operation_intent": intent, "write_tool": write_tool},
            },
            {
                "step_id": "step_confirm_write",
                "kind": "confirm",
                "purpose": "等待用户确认写入操作",
                "input": {"from_session": ["validation.write_payload"]},
                "output": {"save_as": "confirmation.write"},
                "validation": {"required": True},
            },
            {
                "step_id": "step_write_feishu",
                "kind": "tool",
                "tool_name": write_tool,
                "purpose": "执行飞书写入类操作",
                "input": {"from_session": ["validation.write_payload"]},
                "output": {"save_as": "write_result", "content_path": "content[0].text"},
                "validation": {"idempotent": True},
            },
        ],
        "final": {"source": "write_result", "format": "answer"},
    }
