"""tool_ReadFeishuBitableSchema：读取飞书多维表格字段定义的工具。"""

from __future__ import annotations

import json
from typing import Any

try:
    from ..agents.shared.time_utils import now_iso
except ImportError:
    from agents.shared.time_utils import now_iso

from .field_context import load_table_fields_context
from .write_support import content, extract_tool_input_text


# 这一段定义工具名称，必须和 workflowagent 输出的 tool_name 保持一致。
TOOL_NAME = "tool_ReadFeishuBitableSchema"


# 这个函数是字段读取工具入口，输入和输出都使用 content[0].text。
def run_tool_ReadFeishuBitableSchema(payload: dict[str, Any]) -> dict[str, list[dict[str, str]]]:
    original_input = extract_tool_input_text(payload)
    table_fields = load_table_fields_context()
    result = {
        "type": "tool_result",
        "tool_name": TOOL_NAME,
        "service": "feishu_bitable",
        "operation": "read_schema",
        "backend": table_fields.get("source"),
        "mock": table_fields.get("source") == "mock",
        "original_input": original_input,
        "table_fields": {
            "source": table_fields.get("source"),
            "table_name": table_fields.get("table_name"),
            "field_names": table_fields.get("field_names", []),
            "fields": table_fields.get("fields", []),
            "error": table_fields.get("error"),
        },
        "record_count": len(table_fields.get("fields", [])),
        "read_at": now_iso(),
        "summary": _summary(table_fields),
        "warnings": [],
        "error": table_fields.get("error"),
    }
    return content(json.dumps(result, ensure_ascii=False))


# 这个函数生成字段读取摘要，交给后续业务 Agent 或最终答案使用。
def _summary(table_fields: dict[str, Any]) -> str:
    if table_fields.get("error"):
        return f"字段读取失败：{table_fields['error']}"
    source = "真实飞书多维表格" if table_fields.get("source") == "feishu" else "mock 飞书表"
    field_names = table_fields.get("field_names") or []
    return f"已读取{source}字段定义，共 {len(field_names)} 个字段：{'、'.join(field_names)}。"
