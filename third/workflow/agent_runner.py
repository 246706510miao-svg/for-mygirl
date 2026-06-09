"""业务 Agent Runner，负责无状态步骤转换。"""

from __future__ import annotations

import json
from typing import Any

try:
    from ..Tool.write_support import build_write_request
    from ..agents.shared.config import load_config
    from ..agents.workflowagent.agent import CREATE_TOOL, DELETE_TOOL, UPDATE_TOOL
except ImportError:
    from Tool.write_support import build_write_request
    from agents.shared.config import load_config
    from agents.workflowagent.agent import CREATE_TOOL, DELETE_TOOL, UPDATE_TOOL


# 这个函数运行当前步骤指定的业务 Agent；第一版只实现飞书写入 payload 解析。
def run_business_agent(context: dict[str, Any]) -> dict[str, Any]:
    prompt_ref = str(context.get("step", {}).get("prompt_ref") or "")
    if prompt_ref == "parse_feishu_record.v1":
        return _parse_feishu_record(context)
    return {
        "content_text": "当前业务 Agent 暂不支持该 prompt_ref。",
        "data_json": {"error": f"不支持的 prompt_ref：{prompt_ref}"},
        "schema_json": {},
    }


# 这个函数把用户输入转换成飞书写入类 Tool 可使用的结构化 payload。
def _parse_feishu_record(context: dict[str, Any]) -> dict[str, Any]:
    config = load_config()
    original_input = str(context.get("original_input") or "")
    table_schema = context.get("artifacts", {}).get("feishu.table_schema", {}).get("data_json", {})
    table_fields = table_schema.get("table_fields") or {}
    intent = str(context.get("plan", {}).get("intent") or "")
    operation, tool_name, request_key = _operation_mapping(intent)
    write_request = build_write_request(operation, original_input, config, table_fields)
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
    }
    return {
        "content_text": json.dumps(data_json, ensure_ascii=False, default=str),
        "data_json": data_json,
        "schema_json": {"request_key": request_key, "tool_name": tool_name},
    }


# 这个函数根据计划意图映射写入 Tool 和请求字段名。
def _operation_mapping(intent: str) -> tuple[str, str, str]:
    if intent == "delete_feishu_record":
        return "delete_record", DELETE_TOOL, "delete_request"
    if intent == "update_feishu_record":
        return "update_record", UPDATE_TOOL, "update_request"
    return "create_record", CREATE_TOOL, "create_request"
