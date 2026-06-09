"""Tool Dispatcher，统一调用 third Tool。"""

from __future__ import annotations

import json
from typing import Any, Callable

try:
    from ..Tool.tool_CreateFeishuBitableRecord import run_tool_CreateFeishuBitableRecord
    from ..Tool.tool_DeleteFeishuBitableRecord import run_tool_DeleteFeishuBitableRecord
    from ..Tool.tool_ReadFeishuBitable import run_tool_ReadFeishuBitable
    from ..Tool.tool_ReadFeishuBitableSchema import run_tool_ReadFeishuBitableSchema
    from ..Tool.tool_UpdateFeishuBitableRecord import run_tool_UpdateFeishuBitableRecord
    from .content import extract_content_text, load_json_object
except ImportError:
    from Tool.tool_CreateFeishuBitableRecord import run_tool_CreateFeishuBitableRecord
    from Tool.tool_DeleteFeishuBitableRecord import run_tool_DeleteFeishuBitableRecord
    from Tool.tool_ReadFeishuBitable import run_tool_ReadFeishuBitable
    from Tool.tool_ReadFeishuBitableSchema import run_tool_ReadFeishuBitableSchema
    from Tool.tool_UpdateFeishuBitableRecord import run_tool_UpdateFeishuBitableRecord
    from workflow.content import extract_content_text, load_json_object


# 这一段注册当前 runtime 可以分发的 Tool。
TOOL_REGISTRY: dict[str, Callable[[dict[str, Any]], dict[str, list[dict[str, str]]]]] = {
    "tool_ReadFeishuBitableSchema": run_tool_ReadFeishuBitableSchema,
    "tool_ReadFeishuBitable": run_tool_ReadFeishuBitable,
    "tool_CreateFeishuBitableRecord": run_tool_CreateFeishuBitableRecord,
    "tool_UpdateFeishuBitableRecord": run_tool_UpdateFeishuBitableRecord,
    "tool_DeleteFeishuBitableRecord": run_tool_DeleteFeishuBitableRecord,
}


# 这个函数调用步骤声明的 Tool，并把输出整理成 artifact。
def dispatch_tool(context: dict[str, Any]) -> dict[str, Any]:
    step = context["step"]
    tool_name = str(step.get("tool_name") or "")
    tool = TOOL_REGISTRY.get(tool_name)
    if not tool:
        raise ValueError(f"不支持的 Tool：{tool_name}")
    payload = _build_tool_payload(context)
    result = tool(payload)
    content_text = extract_content_text(result)
    data_json = load_json_object(content_text) or {"raw_text": content_text}
    return {
        "content_text": content_text,
        "data_json": data_json,
        "schema_json": {"tool_name": tool_name},
    }


# 这个函数根据 step.input 和 artifact 构造 Tool 输入。
def _build_tool_payload(context: dict[str, Any]) -> dict[str, Any]:
    step = context["step"]
    input_spec = step.get("input_spec_json") or {}
    direct_content = input_spec.get("content")
    if direct_content:
        return {"content": direct_content}

    artifacts = context.get("artifacts") or {}
    if "validation.write_payload" in artifacts:
        validation_data = artifacts["validation.write_payload"].get("data_json") or {}
        tool_input_payload = validation_data.get("tool_input_payload") or {}
        return {"content": [{"text": json.dumps(tool_input_payload, ensure_ascii=False, default=str)}]}

    if artifacts:
        first_artifact = next(iter(artifacts.values()))
        content_text = first_artifact.get("content_text") or json.dumps(first_artifact.get("data_json") or {}, ensure_ascii=False)
        return {"content": [{"text": content_text}]}

    return {"content": [{"text": context.get("original_input", "")}]}
