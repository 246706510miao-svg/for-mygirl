"""tool_ReadFeishuBitable：读取飞书多维表格内容的工具。"""

from __future__ import annotations

import json
import re
from typing import Any

try:
    from ..agents.shared.config import ThirdServiceConfig, load_config
    from ..agents.shared.feishu_schema import DEFAULT_READ_FIELDS, FEISHU_READ_FIELD_SCHEMA, KNOWN_FIELD_ALIASES
    from ..agents.shared.time_utils import now_iso
except ImportError:
    from agents.shared.config import ThirdServiceConfig, load_config
    from agents.shared.feishu_schema import DEFAULT_READ_FIELDS, FEISHU_READ_FIELD_SCHEMA, KNOWN_FIELD_ALIASES
    from agents.shared.time_utils import now_iso

from .feishu_client import FeishuBitableClient, FeishuClientError
from .field_context import load_table_fields_context
from .mock_repository import read_mock_records


# 这一段定义工具名称，必须和 workflow registry / dispatcher 保持一致。
TOOL_NAME = "tool_ReadFeishuBitable"


# 这个函数是工具入口，输入和输出都使用 content[0].text。
def run_tool_ReadFeishuBitable(payload: dict[str, Any]) -> dict[str, list[dict[str, str]]]:
    config = load_config()
    tool_input_text = _extract_tool_input_text(payload)
    original_input, explicit_request = _parse_tool_input(tool_input_text)
    table_fields = load_table_fields_context()
    request = _normalize_read_request(
        explicit_request or _build_read_request(original_input, config, table_fields),
        config,
        table_fields,
    )

    try:
        records, backend = _read_records(request, config)
        result = _build_tool_result(original_input, request, table_fields, records, backend, error=None)
    except FeishuClientError as exc:
        result = _build_tool_result(original_input, request, table_fields, [], "feishu_error", error=str(exc))

    return _content(json.dumps(result, ensure_ascii=False))


# 这个函数把工具输出包装成统一的 content[0].text 结构。
def _content(text: str) -> dict[str, list[dict[str, str]]]:
    return {"content": [{"text": text}]}


# 这个函数提取真正给工具使用的文本，兼容旧 tool_call 包装结构。
def _extract_tool_input_text(payload: dict[str, Any]) -> str:
    text = _extract_content_text(payload)
    tool_call = _load_json_object(text)
    if isinstance(tool_call, dict) and tool_call.get("type") == "tool_call":
        return _extract_content_text(tool_call)
    return text


# 这个函数读取 content[0].text，兼容直接传入 text 的调试场景。
def _extract_content_text(payload: dict[str, Any]) -> str:
    content = payload.get("content") or []
    if content and isinstance(content, list):
        first = content[0] or {}
        if isinstance(first, dict):
            return str(first.get("text") or "").strip()
    return str(payload.get("text") or "").strip()


# 这个函数解析工具输入，支持自然语言和业务 Agent 整理后的读取请求 JSON。
def _parse_tool_input(tool_input_text: str) -> tuple[str, dict[str, Any] | None]:
    payload = _load_json_object(tool_input_text)
    if not isinstance(payload, dict):
        return tool_input_text, None

    read_request = payload.get("read_request")
    original_input = str(
        payload.get("original_input")
        or payload.get("normalized_query")
        or payload.get("query")
        or payload.get("text")
        or tool_input_text
    )
    if isinstance(read_request, dict):
        return original_input, read_request
    return original_input, None


# 这个函数构造工具读取请求，字段贴近飞书查询记录接口。
def _build_read_request(
    user_input: str,
    config: ThirdServiceConfig,
    table_fields: dict[str, Any] | None,
) -> dict[str, Any]:
    table_context = config.table_context
    record_id = _extract_record_id(user_input)
    app_token = _extract_named_token(user_input, "app_token") or _extract_base_app_token(user_input)
    table_id = _extract_named_token(user_input, "table_id") or _extract_table_id(user_input)
    view_id = _extract_named_token(user_input, "view_id") or _extract_view_id(user_input)

    return {
        "operation": "get_record" if record_id else "search_records",
        "service": "feishu_bitable",
        "app_token": app_token or table_context["app_token"],
        "table_id": table_id or table_context["table_id"],
        "table_name": table_context["table_name"],
        "record_id": record_id,
        "view_id": view_id or table_context["view_id"] or None,
        "field_names": _extract_field_names(user_input, table_fields, config),
        "filter": {
            "conjunction": "and",
            "conditions": _extract_filter_conditions(user_input, table_fields, config),
        },
        "sort": _extract_sort(user_input, table_fields, config),
        "page_size": _extract_page_size(user_input),
        "page_token": None,
        "user_id_type": table_context["user_id_type"],
        "automatic_fields": True,
        "mock": not config.feishu_use_real,
        "source_fields": FEISHU_READ_FIELD_SCHEMA,
        "table_fields": table_fields or {},
    }


# 这个函数补齐读取请求字段，防止业务 Agent 或外部调用漏传字段。
def _normalize_read_request(
    read_request: dict[str, Any] | None,
    config: ThirdServiceConfig,
    table_fields: dict[str, Any] | None,
) -> dict[str, Any]:
    request = dict(read_request or {})
    table_context = config.table_context
    default_fields = [] if _field_names_from_context(table_fields) else DEFAULT_READ_FIELDS.copy()
    request.setdefault("operation", "search_records")
    request.setdefault("service", "feishu_bitable")
    request.setdefault("app_token", table_context["app_token"])
    request.setdefault("table_id", table_context["table_id"])
    request.setdefault("table_name", table_context["table_name"])
    request.setdefault("record_id", None)
    request.setdefault("view_id", table_context["view_id"] or None)
    request.setdefault("field_names", default_fields)
    request.setdefault("filter", {"conjunction": "and", "conditions": []})
    request.setdefault("sort", [])
    request.setdefault("page_size", 20)
    request.setdefault("page_token", None)
    request.setdefault("user_id_type", table_context["user_id_type"])
    request.setdefault("automatic_fields", True)
    request.setdefault("mock", not config.feishu_use_real)
    request["table_fields"] = table_fields or {}
    return request


# 这个函数提取形如 app_token: xxx、table_id=xxx 的显式参数。
def _extract_named_token(user_input: str, name: str) -> str | None:
    pattern = rf"{re.escape(name)}\s*[:=：]\s*([A-Za-z0-9_\-]+)"
    match = re.search(pattern, user_input, flags=re.IGNORECASE)
    return match.group(1) if match else None


# 这个函数从飞书 base 链接里提取 app_token。
def _extract_base_app_token(user_input: str) -> str | None:
    match = re.search(r"/base/([A-Za-z0-9_\-]+)", user_input)
    return match.group(1) if match else None


# 这个函数提取 table_id，支持 table_id=tblxxx 或 表=tblxxx。
def _extract_table_id(user_input: str) -> str | None:
    match = re.search(r"(?:table=|table_id=|表=)(tbl[A-Za-z0-9_\-]+)", user_input, flags=re.IGNORECASE)
    return match.group(1) if match else None


# 这个函数提取 view_id，支持 view_id=vewxxx 或 视图=vewxxx。
def _extract_view_id(user_input: str) -> str | None:
    match = re.search(r"(?:view=|view_id=|视图=)(vew[A-Za-z0-9_\-]+)", user_input, flags=re.IGNORECASE)
    return match.group(1) if match else None


# 这个函数提取 record_id，识别显式参数或 rec 开头的记录 id。
def _extract_record_id(user_input: str) -> str | None:
    explicit = _extract_named_token(user_input, "record_id")
    if explicit:
        return explicit
    match = re.search(r"\b(rec[A-Za-z0-9_\-]+)\b", user_input)
    return match.group(1) if match else None


# 这个函数把用户提到的字段归一化成真实表字段名；真实字段存在时不使用本地默认字段。
def _extract_field_names(
    user_input: str,
    table_fields: dict[str, Any] | None,
    config: ThirdServiceConfig,
) -> list[str]:
    available_field_names = _field_names_from_context(table_fields)
    if available_field_names:
        return _extract_real_field_names(user_input, available_field_names, config)

    fields: list[str] = []
    lower_input = user_input.lower()
    for field_name, aliases in KNOWN_FIELD_ALIASES.items():
        if any(alias.lower() in lower_input for alias in aliases):
            fields.append(field_name)

    explicit_match = re.search(r"(?:返回|输出|只看|只返回|字段)\s*[:：]?\s*([^，。；;]+)", user_input)
    if explicit_match:
        fields.extend(_split_explicit_fields(explicit_match.group(1)))

    deduped = _dedupe_keep_order(fields)
    return deduped or DEFAULT_READ_FIELDS.copy()


# 这个函数在真实字段上下文里抽取用户明确提到的字段；没有命中时返回空列表表示读取全部字段。
def _extract_real_field_names(
    user_input: str,
    available_field_names: list[str],
    config: ThirdServiceConfig,
) -> list[str]:
    fields: list[str] = []
    for field_name in available_field_names:
        if field_name and field_name in user_input:
            fields.append(field_name)

    explicit_match = re.search(r"(?:返回|输出|只看|只返回|字段)\s*[:：]?\s*([^，。；;]+)", user_input)
    if explicit_match:
        for field_name in _split_explicit_fields(explicit_match.group(1)):
            resolved = _resolve_table_field_name(field_name, available_field_names, config)
            if resolved:
                fields.append(resolved)

    return _dedupe_keep_order(fields)


# 这个函数拆分“只返回标题、状态”这类显式字段列表。
def _split_explicit_fields(text: str) -> list[str]:
    parts = re.split(r"[,，、\s]+", text)
    normalized: list[str] = []
    alias_to_field = {
        alias.lower(): field_name
        for field_name, aliases in KNOWN_FIELD_ALIASES.items()
        for alias in (field_name, *aliases)
    }
    for part in parts:
        item = part.strip(" .。；;")
        if not item:
            continue
        normalized.append(alias_to_field.get(item.lower(), item))
    return normalized


# 这个函数提取状态、优先级、分类和关键词过滤条件，并在真实字段存在时只使用真实字段。
def _extract_filter_conditions(
    user_input: str,
    table_fields: dict[str, Any] | None,
    config: ThirdServiceConfig,
) -> list[dict[str, Any]]:
    conditions: list[dict[str, Any]] = []
    available_field_names = _field_names_from_context(table_fields)

    status_match = re.search(r"状态(?:为|是|=|：|:)?\s*([^\s，。；;]+)", user_input)
    status_field = _resolve_table_field_name("状态", available_field_names, config)
    if status_match:
        status_value = _normalize_condition_value(status_match.group(1), ["进行中", "已完成", "待开始", "未完成"])
        if status_field:
            conditions.append({"field_name": status_field, "operator": "is", "value": status_value})
    else:
        for status in ("进行中", "已完成", "待开始", "未完成"):
            if status in user_input and status_field:
                conditions.append({"field_name": status_field, "operator": "is", "value": status})
                break

    priority_match = re.search(r"优先级(?:为|是|=|：|:)?\s*([高中低])", user_input)
    priority_field = _resolve_table_field_name("优先级", available_field_names, config)
    if priority_match and priority_field:
        conditions.append({"field_name": priority_field, "operator": "is", "value": priority_match.group(1)})

    category_match = re.search(r"(?:分类|类别|类型)(?:为|是|=|：|:)?\s*([^\s，。；;]+)", user_input)
    category_field = _resolve_table_field_name("分类", available_field_names, config)
    if category_match and category_field:
        category_value = _normalize_condition_value(category_match.group(1), [])
        conditions.append({"field_name": category_field, "operator": "is", "value": category_value})

    keyword_match = re.search(r"(?:包含|关键词|搜索|查找)\s*[:：]?\s*([^\s，。；;]+)", user_input)
    content_field = _resolve_table_field_name("内容", available_field_names, config)
    if keyword_match and content_field:
        conditions.append({"field_name": content_field, "operator": "contains", "value": keyword_match.group(1)})

    return conditions


# 这个函数清理“进行中的记录”这类被自然语言后缀污染的条件值。
def _normalize_condition_value(value: str, known_values: list[str]) -> str:
    stripped = value.strip()
    for known_value in known_values:
        if known_value in stripped:
            return known_value
    return re.sub(r"(的)?记录$", "", stripped)


# 这个函数提取排序条件，真实字段存在时只返回真实表里存在的排序字段。
def _extract_sort(
    user_input: str,
    table_fields: dict[str, Any] | None,
    config: ThirdServiceConfig,
) -> list[dict[str, Any]]:
    available_field_names = _field_names_from_context(table_fields)
    updated_at_field = _resolve_table_field_name("更新时间", available_field_names, config)
    created_at_field = _resolve_table_field_name("创建时间", available_field_names, config)
    deadline_field = _resolve_table_field_name("截止时间", available_field_names, config)

    if ("最新" in user_input or "最近" in user_input) and updated_at_field:
        return [{"field_name": updated_at_field, "desc": True}]
    if "最早" in user_input and created_at_field:
        return [{"field_name": created_at_field, "desc": False}]
    if ("截止" in user_input or "到期" in user_input) and deadline_field:
        return [{"field_name": deadline_field, "desc": False}]
    return []


# 这个函数提取分页大小，并限制在飞书查询记录接口允许的 1 到 500。
def _extract_page_size(user_input: str) -> int:
    match = re.search(r"(?:前|最多|返回)?\s*(\d{1,3})\s*(?:条|个)", user_input)
    if not match:
        return 20
    return max(1, min(int(match.group(1)), 500))


# 这个函数从字段上下文中提取字段名列表，Tool 用它对齐真实字段。
def _field_names_from_context(table_fields: dict[str, Any] | None) -> list[str]:
    if not table_fields:
        return []
    field_names = table_fields.get("field_names") or []
    return [str(field_name) for field_name in field_names if field_name]


# 这个函数把语义字段名解析成真实表字段名；没有真实字段上下文时保留原字段名。
def _resolve_table_field_name(
    field_name: str,
    available_field_names: list[str],
    config: ThirdServiceConfig,
) -> str | None:
    if not field_name:
        return None
    mapped_name = config.feishu_field_name_map.get(field_name, field_name)
    if not available_field_names:
        return mapped_name

    available_set = set(available_field_names)
    if mapped_name in available_set:
        return mapped_name
    if field_name in available_set:
        return field_name
    return None


# 这个函数根据配置选择真实飞书读取或 mock 读取。
def _read_records(request: dict[str, Any], config: ThirdServiceConfig) -> tuple[list[dict[str, Any]], str]:
    if config.feishu_use_real or request.get("mock") is False:
        if not config.can_read_real_feishu:
            missing = "、".join(config.missing_real_feishu_fields)
            raise FeishuClientError(f"真实飞书读取配置不完整，缺少：{missing}")
        client = FeishuBitableClient(config)
        return client.read_records(request), "feishu"

    return read_mock_records(request), "mock"


# 这个函数把读取结果整理成 workflow artifact 可保存的 tool_result。
def _build_tool_result(
    original_input: str,
    request: dict[str, Any],
    table_fields: dict[str, Any],
    records: list[dict[str, Any]],
    backend: str,
    error: str | None,
) -> dict[str, Any]:
    result = {
        "type": "tool_result",
        "tool_name": TOOL_NAME,
        "service": request["service"],
        "operation": request["operation"],
        "backend": backend,
        "mock": backend == "mock",
        "original_input": original_input,
        "request": _safe_request_for_trace(request),
        "table_fields": _safe_table_fields(table_fields),
        "records": records,
        "record_count": len(records),
        "read_at": now_iso(),
        "summary": _summary(original_input, request, records, backend, error),
        "warnings": _field_validation_warnings(request),
    }
    if error:
        result["error"] = error
    return result


# 这个函数去掉 trace 中不需要暴露的冗余字段。
def _safe_request_for_trace(request: dict[str, Any]) -> dict[str, Any]:
    safe_request = dict(request)
    safe_request.pop("app_token", None)
    safe_request.pop("source_fields", None)
    safe_request.pop("table_fields", None)
    return safe_request


# 这个函数压缩字段上下文，避免 tool_result 过大。
def _safe_table_fields(table_fields: dict[str, Any]) -> dict[str, Any]:
    return {
        "source": table_fields.get("source"),
        "table_name": table_fields.get("table_name"),
        "field_names": table_fields.get("field_names", []),
        "error": table_fields.get("error"),
    }


# 这个函数生成一段读取摘要。
def _summary(
    original_input: str,
    request: dict[str, Any],
    records: list[dict[str, Any]],
    backend: str,
    error: str | None,
) -> str:
    if error:
        return f"读取失败：{error}。"
    fields = "全部字段" if not request.get("field_names") else "、".join(request["field_names"])
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


# 这个函数在保留顺序的同时去重字段名。
def _dedupe_keep_order(items: list[str]) -> list[str]:
    seen: set[str] = set()
    deduped: list[str] = []
    for item in items:
        if item not in seen:
            deduped.append(item)
            seen.add(item)
    return deduped


# 这个函数解析 JSON 对象，兼容外部传入 Markdown 代码块的调试情况。
def _load_json_object(content: str) -> dict[str, Any] | None:
    cleaned = content.strip()
    if cleaned.startswith("```"):
        cleaned = re.sub(r"^```(?:json)?", "", cleaned).strip()
        cleaned = re.sub(r"```$", "", cleaned).strip()
    try:
        loaded = json.loads(cleaned)
    except json.JSONDecodeError:
        return None
    return loaded if isinstance(loaded, dict) else None
