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
    request = _normalize_request(parsed[REQUEST_KEY], config)
    actions = request.get("actions") or []
    executed: list[dict[str, Any]] = []
    error: str | None = None
    failed_action: dict[str, Any] | None = None
    failed_action_index: int | None = None
    backend = "mock"
    real_write = config.feishu_use_real or request.get("mock") is False

    for index, action in enumerate(actions, start=1):
        try:
            executed.append(_execute_action(action, request, config))
        except FeishuClientError as exc:
            failed_action = _safe_action(action)
            failed_action_index = index
            error = str(exc)
            break

    if not error and real_write:
        try:
            _refresh_real_field_cache(config, request)
        except FeishuClientError as exc:
            error = f"字段变更已执行，但刷新字段缓存失败：{exc}"

    if real_write:
        backend = "feishu_error" if error else "feishu"
    elif error:
        backend = "mock_error"

    planned_action_count = len(actions)
    executed_action_count = len(executed)
    remaining_action_count = (
        max(planned_action_count - int(failed_action_index or planned_action_count), 0)
        if error
        else 0
    )
    partial_success = bool(error and executed_action_count)

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
        "action_count": executed_action_count,
        "planned_action_count": planned_action_count,
        "executed_action_count": executed_action_count,
        "failed_action_index": failed_action_index,
        "failed_action": failed_action,
        "remaining_action_count": remaining_action_count,
        "partial_success": partial_success,
        "table_fields": _current_table_fields(config, request),
        "read_at": now_iso(),
        "summary": _summary(executed_action_count, planned_action_count, remaining_action_count, backend, error),
        "warnings": ["部分字段变更已经生效，系统不会自动回滚或重试已执行动作。"] if partial_success else [],
    }
    if error:
        result["error"] = error
    return content(json.dumps(result, ensure_ascii=False, default=str))


def _normalize_request(request: dict[str, Any], config: Any) -> dict[str, Any]:
    normalized = dict(request)
    table_context = config.table_context
    normalized.setdefault("operation", "change_fields")
    normalized.setdefault("service", "feishu_bitable")
    normalized.setdefault("app_token", table_context["app_token"])
    normalized.setdefault("table_id", table_context["table_id"])
    normalized.setdefault("table_name", table_context["table_name"])
    normalized.setdefault("view_id", table_context["view_id"] or None)
    normalized.setdefault("user_id_type", table_context["user_id_type"])
    normalized.setdefault("mock", not config.feishu_use_real)
    return normalized


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


def _safe_action(action: dict[str, Any]) -> dict[str, Any]:
    return {
        key: action.get(key)
        for key in ("action", "field_id", "source_field_name", "field_name", "field_type", "type", "reason")
        if action.get(key) is not None
    }


def _summary(
    executed_action_count: int,
    planned_action_count: int,
    remaining_action_count: int,
    backend: str,
    error: str | None,
) -> str:
    if error:
        if executed_action_count:
            return (
                f"字段变更部分完成：已执行 {executed_action_count}/{planned_action_count} 个动作，随后失败：{error}；"
                f"另有 {remaining_action_count} 个动作未执行。已完成动作不会自动回滚。"
            )
        return f"字段变更失败：{error}"
    source = "真实飞书多维表格" if backend == "feishu" else "mock 飞书表"
    return f"已在{source}执行 {executed_action_count} 个字段变更动作。"
