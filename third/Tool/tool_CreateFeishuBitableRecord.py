"""tool_CreateFeishuBitableRecord：新增飞书多维表格记录的工具。"""

from __future__ import annotations

import json
from typing import Any

try:
    from ..agents.shared.config import load_config
    from ..agents.shared.time_utils import now_iso
except ImportError:
    from agents.shared.config import load_config
    from agents.shared.time_utils import now_iso

from .feishu_client import FeishuBitableClient, FeishuClientError
from .field_context import load_table_fields_context
from .mock_repository import create_mock_record
from .write_support import (
    WRITE_REQUEST_KEYS,
    content,
    extract_tool_input_text,
    normalize_write_request,
    parse_tool_request,
    real_write_configuration_error,
    safe_request_for_trace,
    validation_warnings,
)


# 这一段定义工具名称，必须和 workflow registry / dispatcher 保持一致。
TOOL_NAME = "tool_CreateFeishuBitableRecord"
OPERATION = "create_record"
REQUEST_KEY = WRITE_REQUEST_KEYS[OPERATION]


# 这个函数是新增记录工具入口，输入和输出都使用 content[0].text。
def run_tool_CreateFeishuBitableRecord(payload: dict[str, Any]) -> dict[str, list[dict[str, str]]]:
    config = load_config()
    tool_input_text = extract_tool_input_text(payload)
    original_input, explicit_request = parse_tool_request(tool_input_text, REQUEST_KEY)
    table_fields = load_table_fields_context()
    if isinstance(explicit_request, dict) and isinstance(explicit_request.get("records"), list):
        return content(json.dumps(_run_batch_create(original_input, explicit_request, config, table_fields), ensure_ascii=False))

    request = normalize_write_request(OPERATION, explicit_request, original_input, config, table_fields, require_fields=True)
    validation_error = _validation_error(request, config, table_fields)
    if validation_error:
        result = _build_tool_result(original_input, request, None, "validation_error", validation_error)
        return content(json.dumps(result, ensure_ascii=False))

    try:
        record, backend = _create_record(request, config)
        result = _build_tool_result(original_input, request, record, backend, error=None)
    except FeishuClientError as exc:
        result = _build_tool_result(original_input, request, None, "feishu_error", error=str(exc))

    return content(json.dumps(result, ensure_ascii=False))


# 这个函数处理 create_request.records 批量新增，每条记录仍复用单条字段校验。
def _run_batch_create(
    original_input: str,
    explicit_request: dict[str, Any],
    config: Any,
    table_fields: dict[str, Any],
) -> dict[str, Any]:
    normalized_requests: list[dict[str, Any]] = []
    errors: list[str] = []
    common_request = {key: value for key, value in explicit_request.items() if key not in {"records", "fields", "lookup"}}
    for index, record_payload in enumerate(explicit_request.get("records") or [], start=1):
        if not isinstance(record_payload, dict):
            errors.append(f"第 {index} 条新增记录必须是 JSON 对象。")
            continue
        request = normalize_write_request(OPERATION, {**common_request, **record_payload}, original_input, config, table_fields, require_fields=True)
        validation_error = _validation_error(request, config, table_fields)
        if validation_error:
            errors.append(f"第 {index} 条新增记录：{validation_error}")
        normalized_requests.append(request)

    if errors:
        return _build_batch_tool_result(original_input, normalized_requests, [], "validation_error", "；".join(errors))

    records: list[dict[str, Any]] = []
    backend = "mock"
    try:
        for request in normalized_requests:
            record, backend = _create_record(request, config)
            records.append(record)
    except FeishuClientError as exc:
        return _build_batch_tool_result(original_input, normalized_requests, records, "feishu_error", str(exc))
    return _build_batch_tool_result(original_input, normalized_requests, records, backend, error=None)


# 这个函数根据校验结果决定是否允许继续写入。
def _validation_error(request: dict[str, Any], config: Any, table_fields: dict[str, Any]) -> str | None:
    if request.get("validation_errors"):
        return "；".join(request["validation_errors"])
    return real_write_configuration_error(config, table_fields, force_real=request.get("mock") is False)


# 这个函数根据配置选择真实飞书新增或 mock 新增。
def _create_record(request: dict[str, Any], config: Any) -> tuple[dict[str, Any], str]:
    if config.feishu_use_real or request.get("mock") is False:
        client = FeishuBitableClient(config)
        return client.create_record(request), "feishu"
    return create_mock_record(request), "mock"


# 这个函数把新增结果整理成 workflow artifact 可保存的 tool_result。
def _build_tool_result(
    original_input: str,
    request: dict[str, Any],
    record: dict[str, Any] | None,
    backend: str,
    error: str | None,
) -> dict[str, Any]:
    result = {
        "type": "tool_result",
        "tool_name": TOOL_NAME,
        "service": request.get("service", "feishu_bitable"),
        "operation": OPERATION,
        "backend": backend,
        "mock": backend == "mock",
        "original_input": original_input,
        "request": safe_request_for_trace(request),
        "record": record,
        "record_count": 1 if record else 0,
        "read_at": now_iso(),
        "summary": _summary(record, backend, error),
        "warnings": validation_warnings(request),
    }
    if error:
        result["error"] = error
    return result


# 这个函数把批量新增结果整理成 tool_result。
def _build_batch_tool_result(
    original_input: str,
    requests: list[dict[str, Any]],
    records: list[dict[str, Any]],
    backend: str,
    error: str | None,
) -> dict[str, Any]:
    result = {
        "type": "tool_result",
        "tool_name": TOOL_NAME,
        "service": "feishu_bitable",
        "operation": OPERATION,
        "backend": backend,
        "mock": backend == "mock",
        "original_input": original_input,
        "request": {"records": [safe_request_for_trace(request) for request in requests]},
        "records": records,
        "record_count": len(records),
        "read_at": now_iso(),
        "summary": _batch_summary(records, backend, error),
        "warnings": _batch_warnings(requests),
    }
    if records:
        result["record"] = records[-1]
    if error:
        result["error"] = error
    return result


# 这个函数生成新增摘要。
def _summary(record: dict[str, Any] | None, backend: str, error: str | None) -> str:
    if error:
        return f"新增失败：{error}"
    source = "真实飞书多维表格" if backend == "feishu" else "mock 飞书表"
    return f"已在{source}新增 1 条记录，record_id：{record.get('record_id') if record else ''}。"


# 这个函数生成批量新增摘要。
def _batch_summary(records: list[dict[str, Any]], backend: str, error: str | None) -> str:
    if error:
        suffix = f"，已创建 {len(records)} 条记录。" if records else ""
        return f"批量新增失败：{error}{suffix}"
    source = "真实飞书多维表格" if backend == "feishu" else "mock 飞书表"
    record_ids = [str(record.get("record_id") or "") for record in records if record.get("record_id")]
    return f"已在{source}新增 {len(records)} 条记录，record_id：{', '.join(record_ids)}。"


# 这个函数合并批量请求的校验告警。
def _batch_warnings(requests: list[dict[str, Any]]) -> list[str]:
    warnings: list[str] = []
    for index, request in enumerate(requests, start=1):
        warnings.extend([f"第 {index} 条新增记录：{warning}" for warning in validation_warnings(request)])
    return warnings
