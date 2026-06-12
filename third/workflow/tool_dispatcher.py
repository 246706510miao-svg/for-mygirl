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
    tool_name = str(step.get("tool_name") or "")
    input_spec = step.get("input_spec_json") or {}
    direct_content = input_spec.get("content")
    if direct_content:
        return {"content": direct_content}

    artifacts = context.get("artifacts") or {}
    payload_from = input_spec.get("tool_payload_from")
    if isinstance(payload_from, dict):
        value = _artifact_path_value(artifacts, str(payload_from.get("artifact_key") or ""), str(payload_from.get("path") or "data_json"))
        value = _normalize_structured_tool_payload(tool_name, value)
        return {"content": [{"text": json.dumps(value, ensure_ascii=False, default=str)}]}

    if tool_name == "tool_ReadFeishuBitable":
        candidate_payload = _candidate_read_payload_from_artifacts(artifacts)
        if candidate_payload is not None:
            return {"content": [{"text": json.dumps(candidate_payload, ensure_ascii=False, default=str)}]}

    validation_artifact = _validation_artifact(artifacts)
    if validation_artifact:
        validation_data = validation_artifact.get("data_json") or {}
        tool_input_payload = validation_data.get("tool_input_payload") or {}
        return {"content": [{"text": json.dumps(tool_input_payload, ensure_ascii=False, default=str)}]}

    if artifacts:
        first_artifact = next(iter(artifacts.values()))
        content_text = first_artifact.get("content_text") or json.dumps(first_artifact.get("data_json") or {}, ensure_ascii=False)
        return {"content": [{"text": content_text}]}

    return {"content": [{"text": context.get("original_input", "")}]}


def _artifact_path_value(artifacts: dict[str, Any], artifact_key: str, path: str) -> Any:
    artifact = artifacts.get(artifact_key)
    if not artifact:
        raise ValueError(f"缺少 Tool 输入 artifact：{artifact_key}")
    value: Any = artifact
    for part in [item for item in path.split(".") if item]:
        if isinstance(value, dict) and part in value:
            value = value[part]
        else:
            raise ValueError(f"Tool 输入 artifact 路径不存在：{artifact_key}.{path}")
    return value


def _normalize_structured_tool_payload(tool_name: str, value: Any) -> Any:
    if tool_name != "tool_ReadFeishuBitable":
        return value
    if not isinstance(value, dict):
        raise ValueError("tool_ReadFeishuBitable 的结构化输入必须是 JSON 对象。")
    if isinstance(value.get("read_request"), dict):
        return value
    nested = value.get("candidate_read_payload")
    if isinstance(nested, dict) and isinstance(nested.get("read_request"), dict):
        return nested
    raise ValueError("tool_ReadFeishuBitable 的结构化输入缺少 read_request。")


def _candidate_read_payload_from_artifacts(artifacts: dict[str, Any]) -> dict[str, Any] | None:
    for artifact in artifacts.values():
        data_json = artifact.get("data_json") if isinstance(artifact, dict) else None
        if not isinstance(data_json, dict):
            continue
        candidate_payload = data_json.get("candidate_read_payload")
        if isinstance(candidate_payload, dict) and isinstance(candidate_payload.get("read_request"), dict):
            return candidate_payload
    return None


def _validation_artifact(artifacts: dict[str, Any]) -> dict[str, Any] | None:
    if "validation.write_payload" in artifacts:
        return artifacts["validation.write_payload"]
    for artifact_key, artifact in artifacts.items():
        if str(artifact_key).startswith("validation.") and isinstance(artifact, dict):
            data_json = artifact.get("data_json") or {}
            if isinstance(data_json, dict) and isinstance(data_json.get("tool_input_payload"), dict):
                return artifact
    return None
