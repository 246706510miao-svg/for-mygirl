"""tool_UpdateFeishuBitableRecord：改写飞书多维表格记录的工具。"""

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
from .mock_repository import read_mock_records, update_mock_record
from .write_support import (
    WRITE_REQUEST_KEYS,
    build_lookup_read_request,
    build_tool_error,
    content,
    extract_tool_input_text,
    has_structured_request,
    normalize_write_request,
    parse_tool_request,
    real_write_configuration_error,
    safe_request_for_trace,
    validation_warnings,
)


# 这一段定义工具名称，必须和 finagent 输出的 tool_name 保持一致。
TOOL_NAME = "tool_UpdateFeishuBitableRecord"
OPERATION = "update_record"
REQUEST_KEY = WRITE_REQUEST_KEYS[OPERATION]


# 这个函数是更新记录工具入口，输入和输出都使用 content[0].text。
def run_tool_UpdateFeishuBitableRecord(payload: dict[str, Any]) -> dict[str, list[dict[str, str]]]:
    config = load_config()
    tool_input_text = extract_tool_input_text(payload)
    if config.finagent_use_llm and not has_structured_request(tool_input_text, REQUEST_KEY):
        result = build_tool_error(
            TOOL_NAME,
            "strict_input_validation",
            tool_input_text,
            f"THIRD_FINAGENT_USE_LLM=1 时 {TOOL_NAME} 只接受包含 {REQUEST_KEY} 的 JSON 输入。",
            backend="strict_error",
        )
        return content(json.dumps(result, ensure_ascii=False))

    original_input, explicit_request = parse_tool_request(tool_input_text, REQUEST_KEY)
    table_fields = load_table_fields_context()
    request = normalize_write_request(OPERATION, explicit_request, original_input, config, table_fields, require_fields=True)
    validation_error = _validation_error(request, config, table_fields)
    if validation_error:
        result = _build_tool_result(original_input, request, None, "validation_error", validation_error)
        return content(json.dumps(result, ensure_ascii=False))

    try:
        record_id = _locate_record_id(request, config)
        request["record_id"] = record_id
        record, backend = _update_record(request, config)
        result = _build_tool_result(original_input, request, record, backend, error=None)
    except FeishuClientError as exc:
        result = _build_tool_result(original_input, request, None, "feishu_error", error=str(exc))

    return content(json.dumps(result, ensure_ascii=False))


# 这个函数根据字段校验和配置决定是否允许继续更新。
def _validation_error(request: dict[str, Any], config: Any, table_fields: dict[str, Any]) -> str | None:
    if request.get("validation_errors"):
        return "；".join(request["validation_errors"])
    return real_write_configuration_error(config, table_fields, force_real=request.get("mock") is False)


# 这个函数定位待更新记录；没有 record_id 时用搜索条件定位唯一记录。
def _locate_record_id(request: dict[str, Any], config: Any) -> str:
    if request.get("record_id"):
        return str(request["record_id"])

    lookup_filter = request.get("lookup", {}).get("filter", {})
    if not lookup_filter.get("conditions"):
        raise FeishuClientError("更新记录前必须提供 record_id，或提供可以唯一定位记录的查询条件。")

    lookup_request = build_lookup_read_request(request)
    records = _search_records_for_update(lookup_request, config)
    if not records:
        raise FeishuClientError("没有找到可更新的记录，请检查 record_id 或定位条件。")
    if len(records) > 1:
        record_ids = [record.get("record_id") for record in records]
        raise FeishuClientError(f"定位到多条记录，已拒绝更新，请补充更精确条件：{record_ids}")
    return str(records[0]["record_id"])


# 这个函数根据配置选择真实飞书搜索或 mock 搜索来定位更新目标。
def _search_records_for_update(lookup_request: dict[str, Any], config: Any) -> list[dict[str, Any]]:
    if config.feishu_use_real or lookup_request.get("mock") is False:
        client = FeishuBitableClient(config)
        return client.search_records(lookup_request)
    return read_mock_records(lookup_request)


# 这个函数根据配置选择真实飞书更新或 mock 更新。
def _update_record(request: dict[str, Any], config: Any) -> tuple[dict[str, Any], str]:
    if config.feishu_use_real or request.get("mock") is False:
        client = FeishuBitableClient(config)
        return client.update_record(request), "feishu"

    record = update_mock_record(str(request["record_id"]), request.get("fields", {}))
    if not record:
        raise FeishuClientError(f"mock 表中不存在 record_id={request['record_id']} 的记录。")
    return record, "mock"


# 这个函数把更新结果整理成传回 finagent 的 tool_result。
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


# 这个函数生成给 finagent 使用的更新摘要。
def _summary(record: dict[str, Any] | None, backend: str, error: str | None) -> str:
    if error:
        return f"更新失败：{error}"
    source = "真实飞书多维表格" if backend == "feishu" else "mock 飞书表"
    return f"已在{source}更新 1 条记录，record_id：{record.get('record_id') if record else ''}。"
