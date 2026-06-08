"""飞书多维表格 Tool 使用的 mock 数据仓储。"""

from __future__ import annotations

from copy import deepcopy
from typing import Any

try:
    from ..agents.shared.mock_feishu import MOCK_RECORDS
except ImportError:
    from agents.shared.mock_feishu import MOCK_RECORDS


# 这一段定义进程内 mock 表数据，写入类 Tool 会修改它，便于本地联调 CRUD。
MOCK_STORE: list[dict[str, Any]] = deepcopy(MOCK_RECORDS)


# 这个函数用 mock 数据执行读取请求，保持和真实飞书返回的 record 结构一致。
def read_mock_records(request: dict[str, Any]) -> list[dict[str, Any]]:
    records = _select_records(request)
    return [_project_fields(record, request.get("field_names", [])) for record in records]


# 这个函数向 mock 表新增一条记录，并返回类似飞书 record 的结构。
def create_mock_record(request: dict[str, Any]) -> dict[str, Any]:
    record_id = _next_mock_record_id()
    record = {
        "record_id": record_id,
        "fields": dict(request.get("fields") or {}),
    }
    MOCK_STORE.append(record)
    return deepcopy(record)


# 这个函数更新 mock 表中的单条记录。
def update_mock_record(record_id: str, fields: dict[str, Any]) -> dict[str, Any] | None:
    record = _find_record(record_id)
    if not record:
        return None
    record["fields"].update(fields)
    return deepcopy(record)


# 这个函数删除 mock 表中的单条记录，并返回被删除的记录。
def delete_mock_record(record_id: str) -> dict[str, Any] | None:
    for index, record in enumerate(MOCK_STORE):
        if record["record_id"] != record_id:
            continue
        removed = MOCK_STORE.pop(index)
        return deepcopy(removed)
    return None


# 这个函数根据 operation 和 filter 从 mock 数据中筛选记录。
def _select_records(request: dict[str, Any]) -> list[dict[str, Any]]:
    operation = request["operation"]
    if operation == "get_record" and request.get("record_id"):
        records = [record for record in MOCK_STORE if record["record_id"] == request["record_id"]]
    else:
        records = MOCK_STORE.copy()

    for condition in request.get("filter", {}).get("conditions", []):
        records = [record for record in records if _record_matches(record, condition)]

    records = _sort_records(records, request.get("sort", []))
    return records[: int(request.get("page_size") or 20)]


# 这个函数根据 record_id 查找进程内 mock 记录。
def _find_record(record_id: str) -> dict[str, Any] | None:
    for record in MOCK_STORE:
        if record["record_id"] == record_id:
            return record
    return None


# 这个函数生成不会和现有 mock 记录冲突的新 record_id。
def _next_mock_record_id() -> str:
    index = len(MOCK_STORE) + 1
    existing_ids = {record["record_id"] for record in MOCK_STORE}
    while True:
        record_id = f"rec_mock_generated_{index:03d}"
        if record_id not in existing_ids:
            return record_id
        index += 1


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
