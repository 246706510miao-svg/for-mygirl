"""tool_ChangeFeishuBitableFields：变更飞书多维表格字段的工具。"""

from __future__ import annotations

import json
from typing import Any

try:
    from ..agents.shared.config import load_config
    from ..agents.shared.time_utils import now_iso
    from ..workflow.field_cache import save_cached_fields
except ImportError:
    from agents.shared.config import load_config
    from agents.shared.time_utils import now_iso
    from workflow.field_cache import save_cached_fields

from .feishu_client import FeishuBitableClient, FeishuClientError
from .mock_repository import create_mock_field, delete_mock_field, list_mock_field_definitions, update_mock_field
from .write_support import build_tool_error, content, extract_tool_input_text, load_json_object


TOOL_NAME = "tool_ChangeFeishuBitableFields"
REQUEST_KEY = "schema_change_request"


def run_tool_ChangeFeishuBitableFields(payload: dict[str, Any]) -> dict[str, list[dict[str, str]]]:
    config = load_config()
    tool_input_text = extract_tool_input_text(payload)
    parsed = load_json_object(tool_input_text)
    if not isinstance(parsed, dict) or not isinstance(parsed.get(REQUEST_KEY), dict):
        result = build_tool_error(
            TOOL_NAME,
            "change_fields",
            tool_input_text,
            f"{TOOL_NAME} 只接受包含 {REQUEST_KEY} 的 JSON 输入。",
        )
        return content(json.dumps(result, ensure_ascii=False))

    original_input = str(parsed.get("original_input") or tool_input_text)
    request = parsed[REQUEST_KEY]
    actions = request.get("actions") or []
    executed: list[dict[str, Any]] = []
    error: str | None = None
    backend = "mock"

    try:
        for action in actions:
            executed.append(_execute_action(action, request, config))
        if config.feishu_use_real or request.get("mock") is False:
            backend = "feishu"
            _refresh_real_field_cache(config, request)
    except FeishuClientError as exc:
        backend = "feishu_error" if config.feishu_use_real or request.get("mock") is False else "mock_error"
        error = str(exc)

    result = {
        "type": "tool_result",
        "tool_name": TOOL_NAME,
        "service": "feishu_bitable",
        "operation": "change_fields",
        "backend": backend,
        "mock": backend == "mock",
        "original_input": original_input,
        "request": _safe_schema_request(request),
        "actions": executed,
        "action_count": len(executed),
        "table_fields": _current_table_fields(config, request),
        "read_at": now_iso(),
        "summary": _summary(executed, backend, error),
        "warnings": [],
    }
    if error:
        result["error"] = error
    return content(json.dumps(result, ensure_ascii=False, default=str))


def _execute_action(action: dict[str, Any], request: dict[str, Any], config: Any) -> dict[str, Any]:
    action_type = str(action.get("action") or "")
    if config.feishu_use_real or request.get("mock") is False:
        return _execute_real_action(action_type, action, request, config)
    return _execute_mock_action(action_type, action)


def _execute_real_action(action_type: str, action: dict[str, Any], request: dict[str, Any], config: Any) -> dict[str, Any]:
    client = FeishuBitableClient(config)
    action_request = {
        **action,
        "app_token": request["app_token"],
        "table_id": request["table_id"],
    }
    if action_type == "create_field":
        field = client.create_field(action_request)
    elif action_type == "update_field":
        field = client.update_field(action_request)
    elif action_type == "delete_field":
        field = client.delete_field(action_request)
    else:
        raise FeishuClientError(f"不支持的字段变更动作：{action_type}")
    return {"action": action_type, "field": field, "reason": action.get("reason") or ""}


def _execute_mock_action(action_type: str, action: dict[str, Any]) -> dict[str, Any]:
    if action_type == "create_field":
        field = create_mock_field(action)
    elif action_type == "update_field":
        field = update_mock_field(str(action.get("field_id") or ""), action)
        if not field:
            raise FeishuClientError(f"mock 字段不存在：{action.get('field_id')}")
    elif action_type == "delete_field":
        field = delete_mock_field(str(action.get("field_id") or ""))
        if not field:
            raise FeishuClientError(f"mock 字段不存在：{action.get('field_id')}")
    else:
        raise FeishuClientError(f"不支持的字段变更动作：{action_type}")
    return {"action": action_type, "field": field, "reason": action.get("reason") or ""}


def _refresh_real_field_cache(config: Any, request: dict[str, Any]) -> None:
    client = FeishuBitableClient(config)
    fields = client.list_field_definitions(request["app_token"], request["table_id"])
    save_cached_fields(config, fields)


def _current_table_fields(config: Any, request: dict[str, Any]) -> dict[str, Any]:
    if config.feishu_use_real or request.get("mock") is False:
        return {}
    fields = list_mock_field_definitions()
    return {
        "source": "mock",
        "table_name": request.get("table_name"),
        "field_names": [field["field_name"] for field in fields],
        "fields": fields,
    }


def _safe_schema_request(request: dict[str, Any]) -> dict[str, Any]:
    safe_request = dict(request)
    safe_request.pop("app_token", None)
    safe_request.pop("table_fields", None)
    return safe_request


def _summary(actions: list[dict[str, Any]], backend: str, error: str | None) -> str:
    if error:
        suffix = f"，已执行 {len(actions)} 个动作。" if actions else ""
        return f"字段变更失败：{error}{suffix}"
    source = "真实飞书多维表格" if backend == "feishu" else "mock 飞书表"
    return f"已在{source}执行 {len(actions)} 个字段变更动作。"
