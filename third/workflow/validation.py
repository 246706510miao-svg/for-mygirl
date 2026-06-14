"""workflow 写入校验节点。"""

from __future__ import annotations

import hashlib
import json
from copy import deepcopy
from datetime import timedelta
from typing import Any

try:
    from ..Tool.feishu_client import FeishuBitableClient, FeishuClientError
    from ..Tool.mock_repository import read_mock_records
    from ..Tool.write_support import build_lookup_read_request, normalize_write_request, validation_warnings
    from ..agents.shared.config import load_config
    from ..agents.shared.json_utils import dumps_json
    from ..storage.repository import now
    from .registry import CHANGE_SCHEMA_TOOL, CREATE_TOOL, DELETE_TOOL, UPDATE_TOOL
except ImportError:
    from Tool.feishu_client import FeishuBitableClient, FeishuClientError
    from Tool.mock_repository import read_mock_records
    from Tool.write_support import build_lookup_read_request, normalize_write_request, validation_warnings
    from agents.shared.config import load_config
    from agents.shared.json_utils import dumps_json
    from storage.repository import now
    from workflow.registry import CHANGE_SCHEMA_TOOL, CREATE_TOOL, DELETE_TOOL, UPDATE_TOOL


FIELD_TYPE_ALIASES = {
    "text": 1,
    "文本": 1,
    "number": 2,
    "数字": 2,
    "single_select": 3,
    "single": 3,
    "单选": 3,
    "multi_select": 4,
    "multiple_select": 4,
    "多选": 4,
    "date": 5,
    "日期": 5,
    "checkbox": 7,
    "复选框": 7,
    "phone": 13,
    "电话号码": 13,
    "url": 15,
    "链接": 15,
}
SUPPORTED_SCHEMA_FIELD_TYPES = {1, 2, 3, 4, 5, 7, 13, 15}


# 这个函数校验写入 payload，并生成后续 Tool 可直接使用的结构化输入。
def run_validation_node(context: dict[str, Any]) -> dict[str, Any]:
    config = load_config()
    if "feishu.schema_change_payload" in (context.get("artifacts") or {}):
        return _run_schema_change_validation(context, config)
    payload_artifact = _find_payload_artifact(context)
    payload = payload_artifact.get("data_json") or {}
    table_fields = payload.get("table_fields") or _schema_fields(context)
    operation = str(payload.get("operation") or _operation_from_tool(payload.get("tool_name")))
    request_key = str(payload.get("request_key") or _request_key(operation))
    tool_name = str(payload.get("tool_name") or _tool_name(operation))
    original_input = str(context.get("original_input") or "")
    explicit_request = _request_with_record_match((payload.get("tool_input_payload") or {}).get(request_key), context, operation)
    normalized_request, errors = _normalize_validation_request(
        operation,
        explicit_request,
        original_input,
        config,
        table_fields,
        require_fields=operation != "delete_record",
    )
    if operation in {"update_record", "delete_record"}:
        errors.extend(_apply_unique_lookup(normalized_request, operation, config))
    if errors:
        raise ValueError("；".join(errors))

    tool_input_payload = {
        "original_input": original_input,
        request_key: normalized_request,
    }
    idempotency_key, payload_hash = _idempotency_key(operation, tool_input_payload)
    data_json = {
        "tool_name": tool_name,
        "operation": operation,
        "request_key": request_key,
        "tool_input_payload": tool_input_payload,
        "idempotency_key": idempotency_key,
        "payload_hash": payload_hash,
        "warnings": validation_warnings(normalized_request),
        "preview": _preview(normalized_request),
        "expires_at": (now() + timedelta(seconds=config.workflow_idempotency_ttl_seconds)).isoformat(),
    }
    match_info = _match_info(context)
    if match_info:
        data_json["match_info"] = match_info
        data_json["preview"]["match_info"] = match_info
    return {
        "content_text": dumps_json(data_json),
        "data_json": data_json,
        "schema_json": {"operation": operation, "tool_name": tool_name},
    }


# 这个函数校验字段变更 payload，并生成字段变更 Tool 可直接执行的结构化输入。
def _run_schema_change_validation(context: dict[str, Any], config: Any) -> dict[str, Any]:
    payload_artifact = (context.get("artifacts") or {}).get("feishu.schema_change_payload") or {}
    payload = payload_artifact.get("data_json") or {}
    table_fields = payload.get("table_fields") or _schema_fields(context)
    original_input = str(context.get("original_input") or "")
    explicit_request = (payload.get("tool_input_payload") or {}).get("schema_change_request")
    normalized_request, errors = _normalize_schema_change_request(explicit_request, original_input, config, table_fields)
    if errors:
        raise ValueError("；".join(errors))

    tool_input_payload = {
        "original_input": original_input,
        "schema_change_request": normalized_request,
    }
    idempotency_key, payload_hash = _idempotency_key("change_fields", tool_input_payload)
    preview = _schema_change_preview(normalized_request)
    data_json = {
        "tool_name": CHANGE_SCHEMA_TOOL,
        "operation": "change_fields",
        "request_key": "schema_change_request",
        "tool_input_payload": tool_input_payload,
        "idempotency_key": idempotency_key,
        "payload_hash": payload_hash,
        "warnings": [],
        "preview": preview,
        "expires_at": (now() + timedelta(seconds=config.workflow_idempotency_ttl_seconds)).isoformat(),
    }
    return {
        "content_text": dumps_json(data_json),
        "data_json": data_json,
        "schema_json": {"operation": "change_fields", "tool_name": CHANGE_SCHEMA_TOOL},
    }


def _normalize_schema_change_request(
    explicit_request: Any,
    original_input: str,
    config: Any,
    table_fields: dict[str, Any],
) -> tuple[dict[str, Any], list[str]]:
    table_context = config.table_context
    request = dict(explicit_request) if isinstance(explicit_request, dict) else {}
    request.setdefault("operation", "change_fields")
    request.setdefault("service", "feishu_bitable")
    request.setdefault("app_token", table_context["app_token"])
    request.setdefault("table_id", table_context["table_id"])
    request.setdefault("table_name", table_context["table_name"])
    request.setdefault("view_id", table_context["view_id"] or None)
    request.setdefault("user_id_type", table_context["user_id_type"])
    request.setdefault("mock", not config.feishu_use_real)
    request["table_fields"] = table_fields or {}

    errors: list[str] = []
    config_error = _schema_change_configuration_error(config, table_fields, force_real=request.get("mock") is False)
    if config_error:
        errors.append(config_error)

    raw_actions = request.get("actions") or []
    if not isinstance(raw_actions, list) or not raw_actions:
        errors.append("字段变更至少需要一个 action。")
        raw_actions = []

    normalized_actions, action_errors = _normalize_schema_actions(raw_actions, original_input, table_fields)
    errors.extend(action_errors)
    request["actions"] = normalized_actions
    request["validation_errors"] = _dedupe_keep_order(errors)
    return request, request["validation_errors"]


def _schema_change_configuration_error(config: Any, table_fields: dict[str, Any], force_real: bool = False) -> str | None:
    if not config.feishu_use_real and not force_real:
        return None
    if not config.can_write_real_feishu:
        return f"真实飞书字段变更配置不完整，缺少：{'、'.join(config.missing_real_feishu_fields)}"
    if table_fields.get("source") != "feishu":
        return f"无法读取真实飞书表字段，已停止字段变更：{table_fields.get('error') or '字段上下文不可用'}"
    return None


def _normalize_schema_actions(
    raw_actions: list[Any],
    original_input: str,
    table_fields: dict[str, Any],
) -> tuple[list[dict[str, Any]], list[str]]:
    normalized: list[dict[str, Any]] = []
    errors: list[str] = []
    fields_by_name = _field_definitions_by_name(table_fields)
    fields_by_id = _field_definitions_by_id(table_fields)
    planned_names = set(fields_by_name.keys())

    for index, raw_action in enumerate(raw_actions, start=1):
        if not isinstance(raw_action, dict):
            errors.append(f"第 {index} 个字段变更 action 必须是 JSON 对象。")
            continue
        action = str(raw_action.get("action") or "").strip()
        if action == "create_field":
            normalized_action, action_errors = _normalize_create_field_action(raw_action, planned_names)
        elif action == "update_field":
            normalized_action, action_errors = _normalize_update_field_action(raw_action, fields_by_name, fields_by_id, planned_names)
        elif action == "delete_field":
            normalized_action, action_errors = _normalize_delete_field_action(raw_action, original_input, fields_by_name, fields_by_id, planned_names)
        else:
            normalized_action, action_errors = None, [f"第 {index} 个字段变更 action 不受支持：{action}"]
        if action_errors:
            errors.extend([f"第 {index} 个字段变更：{error}" for error in action_errors])
        if normalized_action:
            normalized.append(normalized_action)

    return normalized, errors


def _normalize_create_field_action(raw_action: dict[str, Any], planned_names: set[str]) -> tuple[dict[str, Any] | None, list[str]]:
    errors: list[str] = []
    field_name = str(raw_action.get("field_name") or "").strip()
    field_type, type_error = _normalize_schema_field_type(raw_action.get("field_type") or raw_action.get("type"))
    if not field_name:
        errors.append("新增字段缺少 field_name。")
    if field_name in planned_names:
        errors.append(f"字段 `{field_name}` 已存在。")
    if type_error:
        errors.append(type_error)
    property_config, property_error = _normalize_schema_field_property(field_type, raw_action.get("property"))
    if property_error:
        errors.append(property_error)
    if errors:
        return None, errors
    planned_names.add(field_name)
    return {
        "action": "create_field",
        "field_name": field_name,
        "field_type": _field_type_name(field_type),
        "type": field_type,
        "property": property_config,
        "reason": str(raw_action.get("reason") or "").strip(),
    }, []


def _normalize_update_field_action(
    raw_action: dict[str, Any],
    fields_by_name: dict[str, dict[str, Any]],
    fields_by_id: dict[str, dict[str, Any]],
    planned_names: set[str],
) -> tuple[dict[str, Any] | None, list[str]]:
    errors: list[str] = []
    source = _resolve_schema_field(raw_action, fields_by_name, fields_by_id)
    if not source:
        errors.append("更新字段必须提供存在的 field_id、source_field_name 或 field_name。")
        return None, errors
    old_name = str(source.get("field_name") or "")
    new_name = str(raw_action.get("new_field_name") or raw_action.get("target_field_name") or raw_action.get("field_name") or old_name).strip()
    if raw_action.get("field_type") or raw_action.get("type"):
        requested_type, type_error = _normalize_schema_field_type(raw_action.get("field_type") or raw_action.get("type"))
        if type_error:
            errors.append(type_error)
        elif requested_type != source.get("type"):
            errors.append("第一版不支持修改字段类型。")
    if not new_name:
        errors.append("更新字段缺少目标 field_name。")
    if new_name != old_name and new_name in planned_names:
        errors.append(f"字段 `{new_name}` 已存在，不能重命名为该字段。")
    property_config, property_error = _normalize_schema_field_property(source.get("type"), raw_action.get("property"))
    if property_error:
        errors.append(property_error)
    if errors:
        return None, errors
    if new_name != old_name:
        planned_names.discard(old_name)
        planned_names.add(new_name)
    return {
        "action": "update_field",
        "field_id": source.get("field_id"),
        "source_field_name": old_name,
        "field_name": new_name,
        "type": source.get("type"),
        "property": property_config if raw_action.get("property") is not None else source.get("property") or {},
        "reason": str(raw_action.get("reason") or "").strip(),
    }, []


def _normalize_delete_field_action(
    raw_action: dict[str, Any],
    original_input: str,
    fields_by_name: dict[str, dict[str, Any]],
    fields_by_id: dict[str, dict[str, Any]],
    planned_names: set[str],
) -> tuple[dict[str, Any] | None, list[str]]:
    errors: list[str] = []
    source = _resolve_schema_field(raw_action, fields_by_name, fields_by_id)
    if not source:
        errors.append("删除字段必须提供存在的 field_id、source_field_name 或 field_name。")
        return None, errors
    if not _explicit_field_delete_intent(original_input):
        errors.append("删除字段必须来自用户明确的删除字段意图。")
    if errors:
        return None, errors
    field_name = str(source.get("field_name") or "")
    planned_names.discard(field_name)
    return {
        "action": "delete_field",
        "field_id": source.get("field_id"),
        "field_name": field_name,
        "type": source.get("type"),
        "property": source.get("property") or {},
        "reason": str(raw_action.get("reason") or "").strip(),
    }, []


def _resolve_schema_field(
    action: dict[str, Any],
    fields_by_name: dict[str, dict[str, Any]],
    fields_by_id: dict[str, dict[str, Any]],
) -> dict[str, Any] | None:
    field_id = str(action.get("field_id") or "").strip()
    if field_id and field_id in fields_by_id:
        return fields_by_id[field_id]
    for key in ("source_field_name", "old_field_name", "field_name"):
        field_name = str(action.get(key) or "").strip()
        if field_name and field_name in fields_by_name:
            return fields_by_name[field_name]
    return None


def _normalize_schema_field_type(value: Any) -> tuple[int | None, str | None]:
    if isinstance(value, int):
        field_type = value
    else:
        text = str(value or "text").strip()
        field_type = int(text) if text.isdigit() else FIELD_TYPE_ALIASES.get(text.lower()) or FIELD_TYPE_ALIASES.get(text)
    if field_type not in SUPPORTED_SCHEMA_FIELD_TYPES:
        return None, f"字段类型 `{value}` 暂不支持。"
    return field_type, None


def _normalize_schema_field_property(field_type: Any, property_value: Any) -> tuple[dict[str, Any], str | None]:
    if not isinstance(property_value, dict):
        property_value = {}
    property_config = deepcopy(property_value)
    if field_type not in {3, 4}:
        return property_config, None
    raw_options = property_config.get("options") or []
    if not isinstance(raw_options, list) or not raw_options:
        return property_config, "单选或多选字段必须提供 options。"
    options: list[dict[str, Any]] = []
    seen_names: set[str] = set()
    for option in raw_options:
        name = str(option.get("name") if isinstance(option, dict) else option).strip()
        if not name:
            return property_config, "选项名称不能为空。"
        if name in seen_names:
            return property_config, f"选项 `{name}` 重复。"
        options.append({"name": name})
        seen_names.add(name)
    property_config["options"] = options
    return property_config, None


def _schema_change_preview(request: dict[str, Any]) -> dict[str, Any]:
    actions = [
        {
            "action": action.get("action"),
            "field_id": action.get("field_id"),
            "source_field_name": action.get("source_field_name"),
            "field_name": action.get("field_name"),
            "field_type": action.get("field_type") or _field_type_name(action.get("type")),
            "property": action.get("property") or {},
            "reason": action.get("reason") or "",
        }
        for action in request.get("actions") or []
    ]
    delete_field_names = [action.get("field_name") for action in actions if action.get("action") == "delete_field"]
    return {
        "operation": "change_fields",
        "action_count": len(actions),
        "actions": actions,
        "delete_field_names": delete_field_names,
        "requires_careful_review": bool(delete_field_names),
    }


def _field_definitions_by_id(table_fields: dict[str, Any]) -> dict[str, dict[str, Any]]:
    definitions: dict[str, dict[str, Any]] = {}
    for field in table_fields.get("fields", []) if isinstance(table_fields, dict) else []:
        field_id = field.get("field_id")
        if field_id:
            definitions[str(field_id)] = field
    return definitions


def _field_definitions_by_name(table_fields: dict[str, Any]) -> dict[str, dict[str, Any]]:
    definitions: dict[str, dict[str, Any]] = {}
    for field in table_fields.get("fields", []) if isinstance(table_fields, dict) else []:
        field_name = field.get("field_name")
        if field_name:
            definitions[str(field_name)] = field
    return definitions


def _explicit_field_delete_intent(input_text: str) -> bool:
    return "字段" in input_text and any(keyword in input_text for keyword in ("删除", "移除", "清理"))


def _field_type_name(field_type: Any) -> str:
    return {
        1: "text",
        2: "number",
        3: "single_select",
        4: "multi_select",
        5: "date",
        7: "checkbox",
        13: "phone",
        15: "url",
    }.get(field_type, str(field_type or ""))


def _dedupe_keep_order(items: list[str]) -> list[str]:
    seen: set[str] = set()
    deduped: list[str] = []
    for item in items:
        if item not in seen:
            deduped.append(item)
            seen.add(item)
    return deduped


# 这个函数统一处理单条写入和批量新增写入。
def _normalize_validation_request(
    operation: str,
    explicit_request: dict[str, Any] | None,
    original_input: str,
    config: Any,
    table_fields: dict[str, Any],
    require_fields: bool,
) -> tuple[dict[str, Any], list[str]]:
    if operation == "create_record" and isinstance(explicit_request, dict) and isinstance(explicit_request.get("records"), list):
        return _normalize_batch_create_request(explicit_request, original_input, config, table_fields)
    normalized_request = normalize_write_request(operation, explicit_request, original_input, config, table_fields, require_fields=require_fields)
    return normalized_request, list(normalized_request.get("validation_errors") or [])


# 这个函数把 search_agent 匹配出的 record_id 合并到更新/删除请求中。
def _request_with_record_match(explicit_request: Any, context: dict[str, Any], operation: str) -> dict[str, Any] | None:
    if operation not in {"update_record", "delete_record"}:
        return explicit_request if isinstance(explicit_request, dict) else None
    request = deepcopy(explicit_request) if isinstance(explicit_request, dict) else {}
    matched_record = _matched_record(context)
    if matched_record:
        record_id = str(matched_record.get("record_id") or "").strip()
        if not record_id:
            raise ValueError("search_agent 未输出可用 record_id。")
        request["record_id"] = record_id
    return request


# 这个函数把 create_request.records 中的每条记录分别做字段和类型校验。
def _normalize_batch_create_request(
    explicit_request: dict[str, Any],
    original_input: str,
    config: Any,
    table_fields: dict[str, Any],
) -> tuple[dict[str, Any], list[str]]:
    records = explicit_request.get("records") or []
    common_request = {key: value for key, value in explicit_request.items() if key not in {"records", "fields", "lookup"}}
    normalized_records: list[dict[str, Any]] = []
    errors: list[str] = []
    for index, record_payload in enumerate(records, start=1):
        if not isinstance(record_payload, dict):
            errors.append(f"第 {index} 条新增记录必须是 JSON 对象。")
            continue
        record_request = {**common_request, **record_payload}
        normalized_record = normalize_write_request("create_record", record_request, original_input, config, table_fields, require_fields=True)
        record_errors = list(normalized_record.get("validation_errors") or [])
        if record_errors:
            errors.extend([f"第 {index} 条新增记录：{error}" for error in record_errors])
        normalized_records.append(normalized_record)

    if not normalized_records:
        errors.append("批量新增至少需要一条 records 记录。")

    table_context = config.table_context
    batch_request = {
        "operation": "create_record",
        "service": "feishu_bitable",
        "app_token": common_request.get("app_token") or table_context["app_token"],
        "table_id": common_request.get("table_id") or table_context["table_id"],
        "table_name": common_request.get("table_name") or table_context["table_name"],
        "view_id": common_request.get("view_id") or table_context["view_id"] or None,
        "user_id_type": common_request.get("user_id_type") or table_context["user_id_type"],
        "mock": common_request.get("mock", not config.feishu_use_real),
        "records": normalized_records,
        "table_fields": table_fields,
        "validation_errors": errors,
    }
    return batch_request, errors


# 这个函数从上下文里找到写入 payload artifact。
def _find_payload_artifact(context: dict[str, Any]) -> dict[str, Any]:
    artifacts = context.get("artifacts") or {}
    for artifact_key in ("feishu.create_payload", "feishu.update_payload", "feishu.delete_payload"):
        if artifact_key in artifacts:
            return artifacts[artifact_key]
    raise ValueError("缺少飞书写入 payload artifact。")


# 这个函数从 schema artifact 中提取 table_fields。
def _schema_fields(context: dict[str, Any]) -> dict[str, Any]:
    artifacts = context.get("artifacts", {})
    schema_artifact = artifacts.get("feishu.table_schema_after") or artifacts.get("feishu.table_schema") or {}
    schema_data = schema_artifact.get("data_json") or {}
    return schema_data.get("table_fields") or {}


# 这个函数校验更新和删除是否具备唯一定位条件，并把唯一 record_id 写回请求。
def _apply_unique_lookup(request: dict[str, Any], operation: str, config: Any) -> list[str]:
    if request.get("record_id"):
        return []
    conditions = request.get("lookup", {}).get("filter", {}).get("conditions") or []
    operation_label = "更新" if operation == "update_record" else "删除"
    if not conditions:
        return [f"{operation_label}记录前必须提供 record_id 或 lookup.filter 定位条件。"]
    try:
        records = _search_lookup_records(request, config)
    except FeishuClientError as exc:
        return [f"{operation_label}记录定位失败：{exc}"]
    if not records:
        return [f"没有找到可{operation_label}的记录，请检查定位条件。"]
    if len(records) > 1:
        record_ids = [record.get("record_id") for record in records]
        return [f"定位到多条记录，已拒绝{operation_label}，请补充更精确条件：{record_ids}"]
    request["record_id"] = records[0].get("record_id")
    return []


# 这个函数根据配置使用真实飞书或 mock 查询来验证唯一定位。
def _search_lookup_records(request: dict[str, Any], config: Any) -> list[dict[str, Any]]:
    lookup_request = build_lookup_read_request(request)
    if config.feishu_use_real or lookup_request.get("mock") is False:
        return FeishuBitableClient(config).search_records(lookup_request)
    return read_mock_records(lookup_request)


# 这个函数生成幂等 key 和 payload hash。
def _idempotency_key(operation: str, payload: dict[str, Any]) -> tuple[str, str]:
    normalized = json.dumps(payload, ensure_ascii=False, sort_keys=True, default=str)
    payload_hash = hashlib.sha256(normalized.encode("utf-8")).hexdigest()
    return f"{operation}:feishu_bitable:{payload_hash}", payload_hash


# 这个函数提取确认时展示给用户的数据预览。
def _preview(request: dict[str, Any]) -> dict[str, Any]:
    if isinstance(request.get("records"), list):
        return {
            "record_count": len(request["records"]),
            "records": [
                {
                    "record_id": record.get("record_id"),
                    "fields": record.get("fields") or {},
                    "lookup": record.get("lookup") or {},
                }
                for record in request["records"]
            ],
        }
    return {
        "record_id": request.get("record_id"),
        "fields": request.get("fields") or {},
        "lookup": request.get("lookup") or {},
    }


def _matched_record(context: dict[str, Any]) -> dict[str, Any] | None:
    artifact = (context.get("artifacts") or {}).get("feishu.record_match") or {}
    data_json = artifact.get("data_json") or {}
    matched_record = data_json.get("matched_record")
    return matched_record if isinstance(matched_record, dict) else None


def _match_info(context: dict[str, Any]) -> dict[str, Any] | None:
    matched_record = _matched_record(context)
    if not matched_record:
        return None
    confidence = matched_record.get("confidence")
    confidence_level = str(matched_record.get("confidence_level") or _confidence_level(confidence))
    return {
        "record_id": matched_record.get("record_id"),
        "confidence": confidence,
        "confidence_level": confidence_level,
        "reason": matched_record.get("reason") or "",
        "record_fields": matched_record.get("record_fields") or {},
        "alternative_records": matched_record.get("alternative_records") or [],
        "requires_careful_review": confidence_level == "low",
        "warning": "低置信匹配，请核对后再确认。" if confidence_level == "low" else "",
    }


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


# 这个函数根据 operation 返回 request key。
def _request_key(operation: str) -> str:
    return {
        "create_record": "create_request",
        "update_record": "update_request",
        "delete_record": "delete_request",
    }.get(operation, "create_request")


# 这个函数根据 operation 返回 Tool 名称。
def _tool_name(operation: str) -> str:
    return {
        "create_record": CREATE_TOOL,
        "update_record": UPDATE_TOOL,
        "delete_record": DELETE_TOOL,
    }.get(operation, CREATE_TOOL)


# 这个函数根据 Tool 名称返回 operation。
def _operation_from_tool(tool_name: Any) -> str:
    if tool_name == UPDATE_TOOL:
        return "update_record"
    if tool_name == DELETE_TOOL:
        return "delete_record"
    return "create_record"
