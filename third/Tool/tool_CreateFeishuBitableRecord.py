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
TOOL_NAME = "tool_CreateFeishuBitableRecord"
OPERATION = "create_record"
REQUEST_KEY = WRITE_REQUEST_KEYS[OPERATION]


# 这个函数是新增记录工具入口，输入和输出都使用 content[0].text。
def run_tool_CreateFeishuBitableRecord(payload: dict[str, Any]) -> dict[str, list[dict[str, str]]]:
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
        record, backend = _create_record(request, config)
        result = _build_tool_result(original_input, request, record, backend, error=None)
    except FeishuClientError as exc:
        result = _build_tool_result(original_input, request, None, "feishu_error", error=str(exc))

    return content(json.dumps(result, ensure_ascii=False))


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


# 这个函数把新增结果整理成传回 finagent 的 tool_result。
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


# 这个函数生成给 finagent 使用的新增摘要。
def _summary(record: dict[str, Any] | None, backend: str, error: str | None) -> str:
    if error:
        return f"新增失败：{error}"
    source = "真实飞书多维表格" if backend == "feishu" else "mock 飞书表"
    return f"已在{source}新增 1 条记录，record_id：{record.get('record_id') if record else ''}。"
