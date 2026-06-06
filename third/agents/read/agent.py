"""Read Agent：执行飞书多维表格读取并整理输出。"""

from __future__ import annotations

import json
from typing import Any

from ..shared.config import ThirdServiceConfig, load_config
from ..shared.time_utils import now_iso
from .feishu_client import FeishuBitableClient, FeishuClientError
from .mock_repository import read_mock_records


# 这个函数是 Read Agent 的入口，真实飞书配置完整时读取飞书，否则使用 mock 数据。
def run_read_agent(read_request: dict[str, Any], original_input: str = "") -> dict[str, Any]:
    config = load_config()
    request = _normalize_read_request(read_request, config)
    try:
        records, backend = _read_records(request, config)
        result = _build_result(original_input, request, records, backend, error=None)
    except FeishuClientError as exc:
        result = _build_result(original_input, request, [], "feishu_error", error=str(exc))

    return {
        "read_result": result,
        "output": _format_output(result),
    }


# 这个函数补齐 Read Agent 的请求字段，防止 Router 或外部调用漏传字段。
def _normalize_read_request(read_request: dict[str, Any] | None, config: ThirdServiceConfig) -> dict[str, Any]:
    request = dict(read_request or {})
    table_context = config.table_context
    request.setdefault("operation", "search_records")
    request.setdefault("service", "feishu_bitable")
    request.setdefault("app_token", table_context["app_token"])
    request.setdefault("table_id", table_context["table_id"])
    request.setdefault("table_name", table_context["table_name"])
    request.setdefault("record_id", None)
    request.setdefault("view_id", table_context["view_id"] or None)
    request.setdefault("field_names", ["标题", "内容", "状态", "分类", "优先级", "截止时间"])
    request.setdefault("filter", {"conjunction": "and", "conditions": []})
    request.setdefault("sort", [])
    request.setdefault("page_size", 20)
    request.setdefault("page_token", None)
    request.setdefault("user_id_type", table_context["user_id_type"])
    request.setdefault("automatic_fields", True)
    request.setdefault("mock", not config.feishu_use_real)
    return request


# 这个函数根据配置选择真实飞书读取或 mock 读取。
def _read_records(request: dict[str, Any], config: ThirdServiceConfig) -> tuple[list[dict[str, Any]], str]:
    if config.feishu_use_real or request.get("mock") is False:
        if not config.can_read_real_feishu:
            missing = "、".join(config.missing_real_feishu_fields)
            raise FeishuClientError(f"真实飞书读取配置不完整，缺少：{missing}")
        client = FeishuBitableClient(config)
        return client.read_records(request), "feishu"

    return read_mock_records(request), "mock"


# 这个函数把读取结果整理成 LangGraph 状态里的 read_result。
def _build_result(
    original_input: str,
    request: dict[str, Any],
    records: list[dict[str, Any]],
    backend: str,
    error: str | None,
) -> dict[str, Any]:
    result = {
        "service": request["service"],
        "operation": request["operation"],
        "backend": backend,
        "mock": backend == "mock",
        "request": _safe_request_for_trace(request),
        "records": records,
        "record_count": len(records),
        "read_at": now_iso(),
        "summary": _summary(original_input, request, records, backend, error),
        "warnings": _field_validation_warnings(request),
    }
    if error:
        result["error"] = error
    return result


# 这个函数去掉 trace 中不需要暴露的敏感字段；当前请求本身不包含 app_secret。
def _safe_request_for_trace(request: dict[str, Any]) -> dict[str, Any]:
    safe_request = dict(request)
    return safe_request


# 这个函数生成一段简短中文摘要，方便直接阅读 Read Agent 的结果。
def _summary(
    original_input: str,
    request: dict[str, Any],
    records: list[dict[str, Any]],
    backend: str,
    error: str | None,
) -> str:
    if error:
        return f"读取失败：{error}。"
    fields = "、".join(request["field_names"])
    query = f"原始输入：{original_input}。" if original_input else ""
    source = "真实飞书多维表格" if backend == "feishu" else "mock 飞书表"
    return f"{query}已按 {request['operation']} 读取 {source}，返回 {len(records)} 条记录，字段：{fields}。"


# 这个函数把真实飞书字段校验结果转换成可读告警。
def _field_validation_warnings(request: dict[str, Any]) -> list[str]:
    validation = request.get("field_validation") or {}
    warnings: list[str] = []

    if validation.get("mapped_field_names"):
        warnings.append(f"字段映射已生效：{validation['mapped_field_names']}")
    if validation.get("dropped_field_names"):
        warnings.append(f"这些返回字段在真实飞书表中不存在，已不传给飞书：{validation['dropped_field_names']}")
    if validation.get("dropped_filter_conditions"):
        warnings.append(f"这些过滤条件字段在真实飞书表中不存在，已不传给飞书：{validation['dropped_filter_conditions']}")
    if validation.get("dropped_sort_rules"):
        warnings.append(f"这些排序字段在真实飞书表中不存在，已不传给飞书：{validation['dropped_sort_rules']}")
    if validation.get("available_field_names"):
        warnings.append(f"真实飞书表字段：{validation['available_field_names']}")

    return warnings


# 这个函数把结构化结果转换成最终输出文本，便于当前阶段直接检验。
def _format_output(result: dict[str, Any]) -> str:
    payload = {
        "summary": result["summary"],
        "service": result["service"],
        "operation": result["operation"],
        "backend": result["backend"],
        "mock": result["mock"],
        "record_count": result["record_count"],
        "records": result["records"],
        "warnings": result["warnings"],
    }
    if result.get("error"):
        payload["error"] = result["error"]
    return "Read Agent 输出：\n" + json.dumps(payload, ensure_ascii=False, indent=2)
