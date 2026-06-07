"""tool_ReadFeishuBitable 使用的 mock 数据读取仓储。"""

from __future__ import annotations

from typing import Any

try:
    from ..agents.shared.mock_feishu import MOCK_RECORDS
except ImportError:
    from agents.shared.mock_feishu import MOCK_RECORDS


# 这个函数用 mock 数据执行读取请求，保持和真实飞书返回的 record 结构一致。
def read_mock_records(request: dict[str, Any]) -> list[dict[str, Any]]:
    records = _select_records(request)
    return [_project_fields(record, request.get("field_names", [])) for record in records]


# 这个函数根据 operation 和 filter 从 mock 数据中筛选记录。
def _select_records(request: dict[str, Any]) -> list[dict[str, Any]]:
    operation = request["operation"]
    if operation == "get_record" and request.get("record_id"):
        records = [record for record in MOCK_RECORDS if record["record_id"] == request["record_id"]]
    else:
        records = MOCK_RECORDS.copy()

    for condition in request.get("filter", {}).get("conditions", []):
        records = [record for record in records if _record_matches(record, condition)]

    records = _sort_records(records, request.get("sort", []))
    return records[: int(request.get("page_size") or 20)]


# 这个函数判断单条 mock 记录是否满足过滤条件。
def _record_matches(record: dict[str, Any], condition: dict[str, Any]) -> bool:
    field_name = condition.get("field_name")
    operator = condition.get("operator", "is")
    expected = str(condition.get("value", "")).strip()
    actual = str(record.get("fields", {}).get(field_name, "")).strip()

    if operator in {"is", "equals", "="}:
        if expected == "未完成":
            return actual != "已完成"
        return actual == expected
    if operator in {"contains", "like"}:
        return expected in actual
    if operator in {"not_empty", "exists", "isNotEmpty"}:
        return bool(actual)
    return True


# 这个函数按读取请求里的排序规则对 mock 记录排序。
def _sort_records(records: list[dict[str, Any]], sort_rules: list[dict[str, Any]]) -> list[dict[str, Any]]:
    sorted_records = records
    for rule in reversed(sort_rules or []):
        field_name = rule.get("field_name")
        desc = bool(rule.get("desc"))
        if not field_name:
            continue
        sorted_records = sorted(
            sorted_records,
            key=lambda record: str(record.get("fields", {}).get(field_name, "")),
            reverse=desc,
        )
    return sorted_records


# 这个函数按 field_names 投影字段；空列表表示读取全部字段。
def _project_fields(record: dict[str, Any], field_names: list[str]) -> dict[str, Any]:
    fields = record.get("fields", {})
    if not field_names:
        selected = dict(fields)
    else:
        selected = {field_name: fields.get(field_name) for field_name in field_names if field_name in fields}
    return {
        "record_id": record["record_id"],
        "fields": selected,
    }

