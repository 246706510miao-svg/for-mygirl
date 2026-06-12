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
    from ..agents.workflowagent.agent import CREATE_TOOL, DELETE_TOOL, UPDATE_TOOL
    from ..storage.repository import now
except ImportError:
    from Tool.feishu_client import FeishuBitableClient, FeishuClientError
    from Tool.mock_repository import read_mock_records
    from Tool.write_support import build_lookup_read_request, normalize_write_request, validation_warnings
    from agents.shared.config import load_config
    from agents.shared.json_utils import dumps_json
    from agents.workflowagent.agent import CREATE_TOOL, DELETE_TOOL, UPDATE_TOOL
    from storage.repository import now


# 这个函数校验写入 payload，并生成后续 Tool 可直接使用的结构化输入。
def run_validation_node(context: dict[str, Any]) -> dict[str, Any]:
    config = load_config()
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
    schema_artifact = context.get("artifacts", {}).get("feishu.table_schema") or {}
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
