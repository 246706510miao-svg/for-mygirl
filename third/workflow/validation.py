"""workflow 写入校验节点。"""

from __future__ import annotations

import hashlib
import json
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
    explicit_request = (payload.get("tool_input_payload") or {}).get(request_key)
    normalized_request = normalize_write_request(
        operation,
        explicit_request,
        original_input,
        config,
        table_fields,
        require_fields=operation != "delete_record",
    )
    errors = list(normalized_request.get("validation_errors") or [])
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
    return {
        "content_text": dumps_json(data_json),
        "data_json": data_json,
        "schema_json": {"operation": operation, "tool_name": tool_name},
    }


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
    return {
        "record_id": request.get("record_id"),
        "fields": request.get("fields") or {},
        "lookup": request.get("lookup") or {},
    }


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
