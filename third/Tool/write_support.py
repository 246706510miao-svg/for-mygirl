"""飞书写入类 Tool 共用的请求整理、字段校验和值转换。"""

from __future__ import annotations

import json
import re
from datetime import datetime
from typing import Any

try:
    from ..agents.shared.config import ThirdServiceConfig
    from ..agents.shared.feishu_schema import KNOWN_FIELD_ALIASES
    from ..agents.shared.time_utils import now_iso
except ImportError:
    from agents.shared.config import ThirdServiceConfig
    from agents.shared.feishu_schema import KNOWN_FIELD_ALIASES
    from agents.shared.time_utils import now_iso


# 这一段定义飞书写入类请求名，Tool 会用它校验 strict LLM 模式下的输入。
WRITE_REQUEST_KEYS = {
    "create_record": "create_request",
    "update_record": "update_request",
    "delete_record": "delete_request",
}


# 这一段定义当前第一版可以安全转换的字段类型，复杂字段先拒绝并提示用户。
SUPPORTED_FEISHU_FIELD_TYPES = {1, 2, 3, 4, 5, 7, 13, 15}
COMPLEX_FEISHU_FIELD_TYPES = {11, 17, 18, 19, 20, 21, 22, 23, 1001, 1002, 1003, 1004, 1005}
VALUELESS_OPERATORS = {"isEmpty", "isNotEmpty"}
OPERATOR_ALIASES = {
    "=": "is",
    "==": "is",
    "equals": "is",
    "equal": "is",
    "is": "is",
    "!=": "isNot",
    "is_not": "isNot",
    "isNot": "isNot",
    "contains": "contains",
    "like": "like",
    "in": "in",
    "isEmpty": "isEmpty",
    "isNotEmpty": "isNotEmpty",
}


# 这个函数把 Tool 输出包装成统一的 content[0].text 结构。
def content(text: str) -> dict[str, list[dict[str, str]]]:
    return {"content": [{"text": text}]}


# 这个函数从 finagent 的 tool_call 里提取真正给 Tool 使用的 content[0].text。
def extract_tool_input_text(payload: dict[str, Any]) -> str:
    text = extract_content_text(payload)
    tool_call = load_json_object(text)
    if isinstance(tool_call, dict) and tool_call.get("type") == "tool_call":
        return extract_content_text(tool_call)
    return text


# 这个函数读取 content[0].text，兼容直接传入 text 的本地调试场景。
def extract_content_text(payload: dict[str, Any]) -> str:
    content_items = payload.get("content") or []
    if content_items and isinstance(content_items, list):
        first = content_items[0] or {}
        if isinstance(first, dict):
            return str(first.get("text") or "").strip()
    return str(payload.get("text") or "").strip()


# 这个函数解析 finagent 传来的结构化写入请求。
def parse_tool_request(tool_input_text: str, request_key: str) -> tuple[str, dict[str, Any] | None]:
    payload = load_json_object(tool_input_text)
    if not isinstance(payload, dict):
        return tool_input_text, None

    original_input = str(
        payload.get("original_input")
        or payload.get("normalized_query")
        or payload.get("query")
        or payload.get("text")
        or tool_input_text
    )
    explicit_request = payload.get(request_key)
    if isinstance(explicit_request, dict):
        return original_input, explicit_request
    return original_input, None


# 这个函数校验 strict LLM 模式下 Tool 是否收到了对应的结构化请求。
def has_structured_request(tool_input_text: str, request_key: str) -> bool:
    payload = load_json_object(tool_input_text)
    return isinstance(payload, dict) and isinstance(payload.get(request_key), dict)


# 这个函数生成 strict 或校验失败时的标准 tool_result，错误仍交给 finagent 总结。
def build_tool_error(
    tool_name: str,
    operation: str,
    original_input: str,
    error: str,
    backend: str = "validation_error",
) -> dict[str, Any]:
    return {
        "type": "tool_result",
        "tool_name": tool_name,
        "service": "feishu_bitable",
        "operation": operation,
        "backend": backend,
        "mock": False,
        "original_input": original_input,
        "records": [],
        "record_count": 0,
        "read_at": now_iso(),
        "summary": f"操作失败：{error}",
        "warnings": [],
        "error": error,
    }


# 这个函数从自然语言构造写入类请求，主要用于无 LLM 的规则兜底。
def build_write_request(
    operation: str,
    user_input: str,
    config: ThirdServiceConfig,
    table_fields: dict[str, Any] | None,
) -> dict[str, Any]:
    table_context = config.table_context
    fields = _extract_create_fields(user_input, table_fields, config)
    if operation == "update_record":
        fields = _extract_update_fields(user_input, table_fields, config)

    return {
        "operation": operation,
        "service": "feishu_bitable",
        "app_token": _extract_named_token(user_input, "app_token") or _extract_base_app_token(user_input) or table_context["app_token"],
        "table_id": _extract_named_token(user_input, "table_id") or _extract_table_id(user_input) or table_context["table_id"],
        "table_name": table_context["table_name"],
        "record_id": _extract_record_id(user_input),
        "view_id": _extract_named_token(user_input, "view_id") or _extract_view_id(user_input) or table_context["view_id"] or None,
        "fields": fields,
        "lookup": _build_lookup(user_input, table_fields, config),
        "user_id_type": table_context["user_id_type"],
        "mock": not config.feishu_use_real,
        "table_fields": table_fields or {},
    }


# 这个函数补齐写入请求，并把字段和定位条件整理成真实飞书可接受的结构。
def normalize_write_request(
    operation: str,
    explicit_request: dict[str, Any] | None,
    original_input: str,
    config: ThirdServiceConfig,
    table_fields: dict[str, Any] | None,
    require_fields: bool,
) -> dict[str, Any]:
    generated_request = build_write_request(operation, original_input, config, table_fields)
    request = {**generated_request, **(explicit_request or {})}
    table_context = config.table_context
    request.setdefault("operation", operation)
    request.setdefault("service", "feishu_bitable")
    request.setdefault("app_token", table_context["app_token"])
    request.setdefault("table_id", table_context["table_id"])
    request.setdefault("table_name", table_context["table_name"])
    request.setdefault("record_id", None)
    request.setdefault("view_id", table_context["view_id"] or None)
    request.setdefault("user_id_type", table_context["user_id_type"])
    request.setdefault("mock", not config.feishu_use_real)
    request["table_fields"] = table_fields or {}

    validation_errors: list[str] = []
    if require_fields:
        fields, field_validation, field_errors = prepare_record_fields(request.get("fields"), table_fields, config)
        request["fields"] = fields
        request["field_validation"] = field_validation
        validation_errors.extend(field_errors)
        if not fields:
            validation_errors.append("没有可写入的字段，请提供真实表字段和值。")
    else:
        request["fields"] = {}
        request["field_validation"] = empty_field_validation(table_fields)

    request["lookup"] = normalize_lookup(request, original_input, table_fields, config)
    request["validation_errors"] = _dedupe_keep_order(validation_errors)
    return request


# 这个函数把写入字段解析成真实字段名和值，真实表字段不存在时不会继续提交。
def prepare_record_fields(
    raw_fields: Any,
    table_fields: dict[str, Any] | None,
    config: ThirdServiceConfig,
) -> tuple[dict[str, Any], dict[str, Any], list[str]]:
    validation = empty_field_validation(table_fields)
    errors: list[str] = []
    if not isinstance(raw_fields, dict):
        return {}, validation, ["写入字段必须是 JSON 对象。"]

    field_definitions = _field_definitions_by_name(table_fields)
    prepared: dict[str, Any] = {}
    for raw_name, raw_value in raw_fields.items():
        field_name = _resolve_field_name(raw_name, table_fields, config, validation)
        if not field_name:
            validation["rejected_field_names"].append(str(raw_name))
            errors.append(f"字段 `{raw_name}` 不在当前飞书多维表格中。")
            continue

        field_definition = field_definitions.get(field_name, {})
        value, value_error = _normalize_field_value(raw_value, field_definition)
        if value_error:
            validation["rejected_field_values"].append({"field_name": field_name, "reason": value_error})
            errors.append(f"字段 `{field_name}` 的值不符合要求：{value_error}")
            continue
        prepared[field_name] = value

    return prepared, validation, errors


# 这个函数给没有字段写入的 delete 场景生成空字段校验结果。
def empty_field_validation(table_fields: dict[str, Any] | None) -> dict[str, Any]:
    return {
        "available_field_names": _field_names_from_context(table_fields),
        "mapped_field_names": {},
        "rejected_field_names": [],
        "rejected_field_values": [],
    }


# 这个函数整理更新和删除时的记录定位条件，record_id 优先，filter 用于搜索唯一记录。
def normalize_lookup(
    request: dict[str, Any],
    original_input: str,
    table_fields: dict[str, Any] | None,
    config: ThirdServiceConfig,
) -> dict[str, Any]:
    lookup = request.get("lookup") if isinstance(request.get("lookup"), dict) else {}
    filter_config = lookup.get("filter") or request.get("filter")
    if not isinstance(filter_config, dict):
        filter_config = _build_lookup(original_input, table_fields, config).get("filter", {})

    conditions, dropped = _prepare_lookup_conditions(filter_config.get("conditions", []), table_fields, config)
    return {
        "filter": {
            "conjunction": filter_config.get("conjunction", "and"),
            "conditions": conditions,
        },
        "page_size": min(int(lookup.get("page_size") or request.get("page_size") or 10), 20),
        "dropped_conditions": dropped,
    }


# 这个函数把写入请求转换成搜索记录接口可用的定位请求。
def build_lookup_read_request(request: dict[str, Any]) -> dict[str, Any]:
    lookup = request.get("lookup") or {}
    return {
        "operation": "search_records",
        "service": "feishu_bitable",
        "app_token": request["app_token"],
        "table_id": request["table_id"],
        "table_name": request.get("table_name"),
        "record_id": None,
        "view_id": request.get("view_id"),
        "field_names": [],
        "filter": lookup.get("filter") or {"conjunction": "and", "conditions": []},
        "sort": [],
        "page_size": int(lookup.get("page_size") or 10),
        "page_token": None,
        "user_id_type": request.get("user_id_type"),
        "automatic_fields": True,
        "mock": request.get("mock"),
        "table_fields": request.get("table_fields") or {},
    }


# 这个函数检查真实飞书写入前的最小配置和字段上下文。
def real_write_configuration_error(
    config: ThirdServiceConfig,
    table_fields: dict[str, Any],
    force_real: bool = False,
) -> str | None:
    if not config.feishu_use_real and not force_real:
        return None
    if not config.can_write_real_feishu:
        return f"真实飞书写入配置不完整，缺少：{'、'.join(config.missing_real_feishu_fields)}"
    if table_fields.get("source") != "feishu":
        return f"无法读取真实飞书表字段，已停止写入：{table_fields.get('error') or '字段上下文不可用'}"
    return None


# 这个函数把请求中不适合暴露给 finagent 的敏感字段移除。
def safe_request_for_trace(request: dict[str, Any]) -> dict[str, Any]:
    safe_request = dict(request)
    safe_request.pop("app_token", None)
    safe_request.pop("table_fields", None)
    return safe_request


# 这个函数把字段校验结果转换成可读告警。
def validation_warnings(request: dict[str, Any]) -> list[str]:
    warnings: list[str] = []
    validation = request.get("field_validation") or {}
    lookup = request.get("lookup") or {}
    has_field_issue = False
    if validation.get("mapped_field_names"):
        warnings.append(f"字段映射已生效：{validation['mapped_field_names']}")
    if validation.get("rejected_field_names"):
        has_field_issue = True
        warnings.append(f"这些字段不在当前表中，已拒绝写入：{validation['rejected_field_names']}")
    if validation.get("rejected_field_values"):
        has_field_issue = True
        warnings.append(f"这些字段值未通过校验：{validation['rejected_field_values']}")
    if lookup.get("dropped_conditions"):
        has_field_issue = True
        warnings.append(f"这些定位条件字段不存在，已移除：{lookup['dropped_conditions']}")
    if has_field_issue and validation.get("available_field_names"):
        warnings.append(f"当前表字段：{validation['available_field_names']}")
    return warnings


# 这个函数解析 JSON 对象，兼容模型返回 Markdown 代码块的情况。
def load_json_object(content: str) -> dict[str, Any] | None:
    cleaned = content.strip()
    if cleaned.startswith("```"):
        cleaned = re.sub(r"^```(?:json)?", "", cleaned).strip()
        cleaned = re.sub(r"```$", "", cleaned).strip()
    try:
        loaded = json.loads(cleaned)
    except json.JSONDecodeError:
        return None
    return loaded if isinstance(loaded, dict) else None


# 这个函数提取形如 app_token: xxx、table_id=xxx 的显式参数。
def _extract_named_token(user_input: str, name: str) -> str | None:
    pattern = rf"{re.escape(name)}\s*[:=：]\s*([A-Za-z0-9_\-]+)"
    match = re.search(pattern, user_input, flags=re.IGNORECASE)
    return match.group(1) if match else None


# 这个函数从飞书 base 链接中提取 app_token。
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


# 这个函数从自然语言里提取新增记录字段。
def _extract_create_fields(
    user_input: str,
    table_fields: dict[str, Any] | None,
    config: ThirdServiceConfig,
) -> dict[str, Any]:
    return _extract_assignments(user_input, table_fields, config, operators=("为", "是", "=", "：", ":"))


# 这个函数从自然语言里提取更新字段，优先识别“改成/设为”这类改写语义。
def _extract_update_fields(
    user_input: str,
    table_fields: dict[str, Any] | None,
    config: ThirdServiceConfig,
) -> dict[str, Any]:
    fields = _extract_assignments(user_input, table_fields, config, operators=("改成", "改为", "更新为", "设为", "变成", "调整为"))
    if not fields and _extract_record_id(user_input):
        fields = _extract_create_fields(user_input, table_fields, config)
    return fields


# 这个函数从自然语言里提取字段赋值，供 create 和 update 的规则兜底使用。
def _extract_assignments(
    user_input: str,
    table_fields: dict[str, Any] | None,
    config: ThirdServiceConfig,
    operators: tuple[str, ...],
) -> dict[str, Any]:
    fields: dict[str, Any] = {}
    operator_pattern = "|".join(re.escape(operator) for operator in operators)
    for field_name, aliases in _field_candidates(table_fields).items():
        for alias in aliases:
            pattern = rf"{re.escape(alias)}\s*(?:{operator_pattern})\s*([^，。；;\n]+)"
            match = re.search(pattern, user_input, flags=re.IGNORECASE)
            if not match:
                continue
            resolved = _resolve_field_name(field_name, table_fields, config, empty_field_validation(table_fields)) or field_name
            fields[resolved] = _clean_extracted_value(match.group(1))
            break
    return fields


# 这个函数根据自然语言构造更新或删除记录的搜索定位条件。
def _build_lookup(
    user_input: str,
    table_fields: dict[str, Any] | None,
    config: ThirdServiceConfig,
) -> dict[str, Any]:
    raw_conditions: list[dict[str, Any]] = []
    operator_pattern = "|".join(re.escape(operator) for operator in ("为", "是", "=", "：", ":"))
    for field_name, aliases in _field_candidates(table_fields).items():
        for alias in aliases:
            pattern = rf"{re.escape(alias)}\s*(?:{operator_pattern})\s*([^，。；;\n]+)"
            match = re.search(pattern, user_input, flags=re.IGNORECASE)
            if not match:
                continue
            raw_conditions.append({"field_name": field_name, "operator": "is", "value": _clean_extracted_value(match.group(1))})
            break

    conditions, dropped = _prepare_lookup_conditions(raw_conditions, table_fields, config)
    return {
        "filter": {"conjunction": "and", "conditions": conditions},
        "page_size": 10,
        "dropped_conditions": dropped,
    }


# 这个函数把定位条件里的字段名和 operator 整理成飞书 search records 可接受的格式。
def _prepare_lookup_conditions(
    raw_conditions: list[dict[str, Any]],
    table_fields: dict[str, Any] | None,
    config: ThirdServiceConfig,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    conditions: list[dict[str, Any]] = []
    dropped: list[dict[str, Any]] = []
    for condition in raw_conditions or []:
        field_name = _resolve_field_name(condition.get("field_name"), table_fields, config, empty_field_validation(table_fields))
        if not field_name:
            dropped.append(condition)
            continue
        operator = _normalize_operator(condition.get("operator"))
        prepared = {"field_name": field_name, "operator": operator}
        if operator not in VALUELESS_OPERATORS:
            value = condition.get("value")
            if value in (None, ""):
                dropped.append(condition)
                continue
            prepared["value"] = value
        conditions.append(prepared)
    return conditions, dropped


# 这个函数生成可用于自然语言抽取的字段候选词。
def _field_candidates(table_fields: dict[str, Any] | None) -> dict[str, tuple[str, ...]]:
    candidates: dict[str, tuple[str, ...]] = {}
    for field_name in _field_names_from_context(table_fields):
        candidates[field_name] = (field_name,)
    for field_name, aliases in KNOWN_FIELD_ALIASES.items():
        candidates.setdefault(field_name, (field_name, *aliases))
    return candidates


# 这个函数把用户输入里提取到的字段值去掉自然语言后缀。
def _clean_extracted_value(value: str) -> str:
    cleaned = value.strip(" \t\r\n，。；;")
    for separator in ("的", "并", "然后"):
        if separator in cleaned:
            cleaned = cleaned.split(separator, 1)[0]
    return cleaned.strip(" \t\r\n，。；;")


# 这个函数从字段上下文中取字段名列表。
def _field_names_from_context(table_fields: dict[str, Any] | None) -> list[str]:
    if not table_fields:
        return []
    return [str(field_name) for field_name in table_fields.get("field_names", []) if field_name]


# 这个函数把字段定义列表转成按字段名索引的字典。
def _field_definitions_by_name(table_fields: dict[str, Any] | None) -> dict[str, dict[str, Any]]:
    definitions: dict[str, dict[str, Any]] = {}
    if not table_fields:
        return definitions
    for field in table_fields.get("fields", []):
        field_name = field.get("field_name")
        if field_name:
            definitions[str(field_name)] = field
    return definitions


# 这个函数把语义字段名或别名解析成真实飞书字段名。
def _resolve_field_name(
    field_name: Any,
    table_fields: dict[str, Any] | None,
    config: ThirdServiceConfig,
    validation: dict[str, Any],
) -> str | None:
    if not field_name:
        return None
    original = str(field_name).strip()
    available_names = _field_names_from_context(table_fields)
    available_set = set(available_names)
    alias_to_field = {
        alias.lower(): canonical
        for canonical, aliases in KNOWN_FIELD_ALIASES.items()
        for alias in (canonical, *aliases)
    }
    canonical = alias_to_field.get(original.lower(), original)
    mapped = config.feishu_field_name_map.get(original) or config.feishu_field_name_map.get(canonical) or canonical

    if not available_names:
        if mapped != original:
            validation["mapped_field_names"][original] = mapped
        return mapped
    if mapped in available_set:
        if mapped != original:
            validation["mapped_field_names"][original] = mapped
        return mapped
    if original in available_set:
        return original
    stripped_available = {name.strip(): name for name in available_names}
    if mapped in stripped_available:
        resolved = stripped_available[mapped]
        if resolved != original:
            validation["mapped_field_names"][original] = resolved
        return resolved
    return None


# 这个函数把字段值转换成当前支持的飞书字段值格式。
def _normalize_field_value(value: Any, field_definition: dict[str, Any]) -> tuple[Any, str | None]:
    field_type = field_definition.get("type")
    if field_type in (None, "mock"):
        return value, None
    if not isinstance(field_type, int):
        return value, None
    if field_type in COMPLEX_FEISHU_FIELD_TYPES:
        return None, f"字段类型 {field_type} 暂未支持自动写入，请改用飞书要求的结构化值。"
    if field_type not in SUPPORTED_FEISHU_FIELD_TYPES:
        return None, f"字段类型 {field_type} 暂未支持自动写入。"
    if field_type == 1:
        return str(value), None
    if field_type == 2:
        return _to_number(value)
    if field_type == 3:
        return str(value), None
    if field_type == 4:
        if isinstance(value, list):
            return [str(item) for item in value], None
        return [str(value)], None
    if field_type == 5:
        return _to_date_millis(value)
    if field_type == 7:
        return _to_bool(value)
    if field_type == 13:
        return str(value), None
    if field_type == 15:
        return _to_url(value)
    return value, None


# 这个函数把数字字段值转换成 int 或 float。
def _to_number(value: Any) -> tuple[int | float | None, str | None]:
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        return value, None
    try:
        number = float(str(value).strip())
    except ValueError:
        return None, "需要数字值。"
    if number.is_integer():
        return int(number), None
    return number, None


# 这个函数把日期字符串转换成飞书日期字段常用的毫秒时间戳。
def _to_date_millis(value: Any) -> tuple[int | None, str | None]:
    if isinstance(value, int):
        return value, None
    if isinstance(value, float):
        return int(value), None
    text = str(value).strip()
    for date_format in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%d %H:%M", "%Y-%m-%d", "%Y/%m/%d"):
        try:
            parsed = datetime.strptime(text, date_format)
        except ValueError:
            continue
        return int(parsed.timestamp() * 1000), None
    return None, "日期请使用 YYYY-MM-DD 或 YYYY-MM-DD HH:MM:SS。"


# 这个函数把中文或字符串布尔值转换成布尔类型。
def _to_bool(value: Any) -> tuple[bool | None, str | None]:
    if isinstance(value, bool):
        return value, None
    text = str(value).strip().lower()
    if text in {"true", "1", "yes", "on", "是", "对", "已完成", "完成"}:
        return True, None
    if text in {"false", "0", "no", "off", "否", "不", "未完成"}:
        return False, None
    return None, "复选框字段需要布尔值。"


# 这个函数把 URL 字段值整理成飞书 URL 字段常用结构。
def _to_url(value: Any) -> tuple[Any, str | None]:
    if isinstance(value, dict):
        return value, None
    text = str(value).strip()
    if not text:
        return None, "URL 不能为空。"
    return {"link": text, "text": text}, None


# 这个函数把常见 operator 别名改成飞书合法 operator。
def _normalize_operator(operator: Any) -> str:
    normalized = str(operator or "is").strip()
    return OPERATOR_ALIASES.get(normalized, "is")


# 这个函数在保留顺序的同时去重。
def _dedupe_keep_order(items: list[str]) -> list[str]:
    seen: set[str] = set()
    deduped: list[str] = []
    for item in items:
        if item not in seen:
            deduped.append(item)
            seen.add(item)
    return deduped
