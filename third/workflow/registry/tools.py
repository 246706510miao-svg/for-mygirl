"""Tool capability registry for workflow planning and validation."""

from __future__ import annotations

from typing import Any


READ_SCHEMA_TOOL = "tool_ReadFeishuBitableSchema"
READ_TOOL = "tool_ReadFeishuBitable"
CREATE_TOOL = "tool_CreateFeishuBitableRecord"
UPDATE_TOOL = "tool_UpdateFeishuBitableRecord"
DELETE_TOOL = "tool_DeleteFeishuBitableRecord"
CHANGE_SCHEMA_TOOL = "tool_ChangeFeishuBitableFields"

WRITE_TOOLS = {CREATE_TOOL, UPDATE_TOOL, DELETE_TOOL, CHANGE_SCHEMA_TOOL}
ALLOWED_TOOLS = {READ_SCHEMA_TOOL, READ_TOOL, CREATE_TOOL, UPDATE_TOOL, DELETE_TOOL, CHANGE_SCHEMA_TOOL}


TOOL_CATALOG: list[dict[str, Any]] = [
    {
        "tool_name": READ_SCHEMA_TOOL,
        "category": "feishu_bitable_schema",
        "side_effect_level": "read",
        "purpose": "读取当前飞书多维表格字段定义，返回可用字段名、字段类型、选项和表信息。",
        "when_to_use": "所有记录写入、字段变更和需要了解表结构的 workflow 的第一步；字段变更后也用于刷新 schema。",
        "input_contract": {"content": [{"text": "读取或刷新当前飞书多维表格字段定义"}]},
        "output_artifact": "feishu.table_schema",
        "output_summary": "table_fields，包含 field_names、fields、字段类型和选项。",
        "requires_confirmation": False,
        "dispatcher_function": "run_tool_ReadFeishuBitableSchema",
    },
    {
        "tool_name": READ_TOOL,
        "category": "feishu_bitable_records",
        "side_effect_level": "read",
        "purpose": "查询或读取飞书多维表格已有记录。",
        "when_to_use": "用户明确要求查询、读取、搜索、列出已有飞书记录时使用；更新或删除已有记录时，也用于读取候选记录交给 search_agent 匹配。",
        "input_contract": {
            "read_request": {
                "operation": "search_records",
                "field_names": [],
                "filter": {"conjunction": "and", "conditions": []},
                "sort": [],
                "page_size": 20,
            }
        },
        "output_artifact": "feishu.records",
        "output_summary": "records、record_count、summary 和字段校验信息。",
        "requires_confirmation": False,
        "dispatcher_function": "run_tool_ReadFeishuBitable",
    },
    {
        "tool_name": CREATE_TOOL,
        "category": "feishu_bitable_write",
        "side_effect_level": "write",
        "purpose": "新增飞书多维表格记录。",
        "when_to_use": "用户要求新增、保存、记录、写到飞书且不是修改或删除已有记录时使用。",
        "input_contract": {
            "from_session": ["validation.write_payload"],
            "payload_shape": {
                "create_request": {
                    "fields": "单条新增字段对象",
                    "records": "可选；批量新增时为数组，每个元素包含 fields",
                }
            },
        },
        "output_artifact": "write_result",
        "output_summary": "新增结果、record_id、summary。",
        "requires_confirmation": True,
        "dispatcher_function": "run_tool_CreateFeishuBitableRecord",
    },
    {
        "tool_name": UPDATE_TOOL,
        "category": "feishu_bitable_write",
        "side_effect_level": "write",
        "purpose": "更新飞书多维表格已有记录。",
        "when_to_use": "用户要求修改、更新、改成、调整已有记录时使用；payload 必须有 record_id 或 lookup.filter 供 validation 唯一定位。",
        "input_contract": {"from_session": ["validation.write_payload"]},
        "output_artifact": "write_result",
        "output_summary": "更新结果、record_id、summary。",
        "requires_confirmation": True,
        "dispatcher_function": "run_tool_UpdateFeishuBitableRecord",
    },
    {
        "tool_name": DELETE_TOOL,
        "category": "feishu_bitable_write",
        "side_effect_level": "delete",
        "purpose": "删除飞书多维表格已有记录。",
        "when_to_use": "用户明确要求删除、移除、清理已有记录时使用；payload 必须有 record_id 或 lookup.filter 供 validation 唯一定位。",
        "input_contract": {"from_session": ["validation.write_payload"]},
        "output_artifact": "write_result",
        "output_summary": "删除结果、record_id、summary。",
        "requires_confirmation": True,
        "dispatcher_function": "run_tool_DeleteFeishuBitableRecord",
    },
    {
        "tool_name": CHANGE_SCHEMA_TOOL,
        "category": "feishu_bitable_schema",
        "side_effect_level": "write",
        "purpose": "变更飞书多维表格字段，包括新增字段、重命名字段、调整单选/多选选项和删除字段。",
        "when_to_use": "用户明确要求新增字段、删除字段、重命名字段、调整字段选项，或要求把当前表结构改造成能记录日报、周报、月报等新结构时使用。",
        "input_contract": {
            "from_session": ["validation.schema_change_payload"],
            "payload_shape": {
                "schema_change_request": {
                    "operation": "change_fields",
                    "actions": "字段变更动作数组",
                }
            },
        },
        "output_artifact": "feishu.schema_change_result",
        "output_summary": "字段变更结果、执行的 actions、summary。",
        "requires_confirmation": True,
        "dispatcher_function": "run_tool_ChangeFeishuBitableFields",
    },
]
