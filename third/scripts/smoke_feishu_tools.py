"""逐个验证六个飞书 Tool；真实写测试只操作并清理临时字段和记录。"""

from __future__ import annotations

import argparse
import json
import uuid
from typing import Any, Callable

from third.Tool.feishu_client import FeishuBitableClient
from third.Tool.tool_ChangeFeishuBitableFields import run_tool_ChangeFeishuBitableFields
from third.Tool.tool_CreateFeishuBitableRecord import run_tool_CreateFeishuBitableRecord
from third.Tool.tool_DeleteFeishuBitableRecord import run_tool_DeleteFeishuBitableRecord
from third.Tool.tool_ReadFeishuBitable import run_tool_ReadFeishuBitable
from third.Tool.tool_ReadFeishuBitableSchema import run_tool_ReadFeishuBitableSchema
from third.Tool.tool_UpdateFeishuBitableRecord import run_tool_UpdateFeishuBitableRecord
from third.agents.shared.config import load_config


ToolFunction = Callable[[dict[str, Any]], dict[str, list[dict[str, str]]]]


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--allow-write",
        action="store_true",
        help="在配置的飞书表中创建并清理临时字段和临时记录，以验证四个写 Tool。",
    )
    args = parser.parse_args()
    config = load_config()
    report: list[dict[str, Any]] = []

    schema = _invoke(run_tool_ReadFeishuBitableSchema, "读取连接测试")
    _record(report, schema)
    read_result = _invoke(
        run_tool_ReadFeishuBitable,
        {
            "original_input": "读取连接测试",
            "read_request": {
                "operation": "search_records",
                "field_names": [],
                "filter": {"conjunction": "and", "conditions": []},
                "sort": [],
                "page_size": 1,
                "automatic_fields": True,
            },
        },
    )
    _record(report, read_result)

    if not args.allow_write:
        for tool_name in (
            "tool_CreateFeishuBitableRecord",
            "tool_UpdateFeishuBitableRecord",
            "tool_DeleteFeishuBitableRecord",
            "tool_ChangeFeishuBitableFields",
        ):
            report.append({"tool": tool_name, "status": "skipped", "reason": "需要 --allow-write"})
        print(json.dumps(report, ensure_ascii=False, indent=2))
        return

    suffix = uuid.uuid4().hex[:8]
    field_name = f"__Tool连接测试_{suffix}"
    renamed_field_name = f"{field_name}_已更新"
    marker = f"tool-smoke-{suffix}"
    record_id: str | None = None
    field_id: str | None = None
    client = FeishuBitableClient(config)
    table_context = config.table_context

    try:
        field_create = _invoke(
            run_tool_ChangeFeishuBitableFields,
            {
                "original_input": "创建临时字段连接测试",
                "schema_change_request": {
                    "operation": "change_fields",
                    "actions": [
                        {
                            "action": "create_field",
                            "field_name": field_name,
                            "type": 1,
                            "property": {},
                            "reason": "Tool 连接测试，完成后自动删除",
                        }
                    ],
                },
            },
        )
        _assert_success(field_create)
        field_id = str(field_create["actions"][0]["field"]["field_id"])

        create_result = _invoke(
            run_tool_CreateFeishuBitableRecord,
            {
                "original_input": "创建临时记录连接测试",
                "create_request": {"fields": {field_name: marker}},
            },
        )
        _assert_success(create_result)
        _record(report, create_result)
        record_id = str(create_result["record"]["record_id"])

        update_result = _invoke(
            run_tool_UpdateFeishuBitableRecord,
            {
                "original_input": "更新临时记录连接测试",
                "update_request": {
                    "record_id": record_id,
                    "fields": {field_name: f"{marker}-updated"},
                },
            },
        )
        _assert_success(update_result)
        _record(report, update_result)

        delete_result = _invoke(
            run_tool_DeleteFeishuBitableRecord,
            {
                "original_input": "删除临时记录连接测试",
                "delete_request": {"record_id": record_id},
            },
        )
        _assert_success(delete_result)
        _record(report, delete_result)
        record_id = None

        field_update = _invoke(
            run_tool_ChangeFeishuBitableFields,
            {
                "original_input": "更新临时字段连接测试",
                "schema_change_request": {
                    "operation": "change_fields",
                    "actions": [
                        {
                            "action": "update_field",
                            "field_id": field_id,
                            "field_name": renamed_field_name,
                            "type": 1,
                            "property": {},
                            "reason": "Tool 连接测试",
                        }
                    ],
                },
            },
        )
        _assert_success(field_update)

        field_delete = _invoke(
            run_tool_ChangeFeishuBitableFields,
            {
                "original_input": "删除临时字段连接测试",
                "schema_change_request": {
                    "operation": "change_fields",
                    "actions": [
                        {
                            "action": "delete_field",
                            "field_id": field_id,
                            "field_name": renamed_field_name,
                            "reason": "清理 Tool 连接测试字段",
                        }
                    ],
                },
            },
        )
        _assert_success(field_delete)
        _record(report, field_delete, stages=["create_field", "update_field", "delete_field"])
        field_id = None
    finally:
        if record_id:
            client.delete_record(
                {
                    **table_context,
                    "record_id": record_id,
                    "user_id_type": config.feishu_user_id_type,
                }
            )
        if field_id:
            client.delete_field({**table_context, "field_id": field_id, "field_name": renamed_field_name})

    print(json.dumps(report, ensure_ascii=False, indent=2))


def _invoke(tool: ToolFunction, payload: str | dict[str, Any]) -> dict[str, Any]:
    text = payload if isinstance(payload, str) else json.dumps(payload, ensure_ascii=False)
    result = tool({"content": [{"text": text}]})
    return json.loads(result["content"][0]["text"])


def _assert_success(result: dict[str, Any]) -> None:
    if result.get("error") or result.get("backend") in {"validation_error", "feishu_error", "mock_error"}:
        raise RuntimeError(f"{result.get('tool_name')} 连接测试失败：{result.get('error') or result.get('summary')}")


def _record(report: list[dict[str, Any]], result: dict[str, Any], **extra: Any) -> None:
    _assert_success(result)
    report.append(
        {
            "tool": result.get("tool_name"),
            "status": "success",
            "backend": result.get("backend"),
            **extra,
        }
    )


if __name__ == "__main__":
    main()
