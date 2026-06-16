"""Workflow template registry and deterministic plan builders."""

from __future__ import annotations

import json
import re
from typing import Any

from .tools import CHANGE_SCHEMA_TOOL, CREATE_TOOL, DELETE_TOOL, READ_SCHEMA_TOOL, READ_TOOL, UPDATE_TOOL


PARSE_FEISHU_RECORD_PROMPT = "parse_feishu_record.v1"
SEARCH_FEISHU_RECORD_PROMPT = "search_feishu_record.v1"
PARSE_FEISHU_SCHEMA_CHANGE_PROMPT = "parse_feishu_schema_change.v1"
SUMMARIZE_WORKFLOW_MISTAKE_PROMPT = "summarize_workflow_mistake.v1"

READ_RECORDS_TEMPLATE = "read_records"
CREATE_RECORD_TEMPLATE = "create_record"
UPDATE_RECORD_TEMPLATE = "update_record"
DELETE_RECORD_TEMPLATE = "delete_record"
CHANGE_SCHEMA_TEMPLATE = "change_schema"
CHANGE_SCHEMA_THEN_CREATE_RECORD_TEMPLATE = "change_schema_then_create_record"
REVIEW_WORKFLOW_MISTAKE_TEMPLATE = "review_workflow_mistake"

TEMPLATE_CATALOG: list[dict[str, Any]] = [
    {
        "template_key": READ_RECORDS_TEMPLATE,
        "intent": "read_feishu_records",
        "risk_level": "read",
        "purpose": "查询或读取飞书记录。",
        "step_order": ["read_records"],
    },
    {
        "template_key": CREATE_RECORD_TEMPLATE,
        "intent": "create_feishu_record",
        "risk_level": "write",
        "purpose": "新增飞书记录。",
        "step_order": ["read_schema", "parse_payload", "validate_payload", "confirm_write", "write_feishu"],
    },
    {
        "template_key": UPDATE_RECORD_TEMPLATE,
        "intent": "update_feishu_record",
        "risk_level": "write",
        "purpose": "更新飞书已有记录。",
        "step_order": [
            "read_schema",
            "parse_payload",
            "read_candidate_records",
            "match_record",
            "validate_payload",
            "confirm_write",
            "write_feishu",
        ],
    },
    {
        "template_key": DELETE_RECORD_TEMPLATE,
        "intent": "delete_feishu_record",
        "risk_level": "delete",
        "purpose": "删除飞书已有记录。",
        "step_order": [
            "read_schema",
            "parse_payload",
            "read_candidate_records",
            "match_record",
            "validate_payload",
            "confirm_write",
            "write_feishu",
        ],
    },
    {
        "template_key": CHANGE_SCHEMA_TEMPLATE,
        "intent": "change_feishu_schema",
        "risk_level": "write",
        "purpose": "变更飞书字段结构。",
        "step_order": [
            "read_schema",
            "parse_schema_change",
            "validate_schema_change",
            "confirm_schema_change",
            "change_fields",
            "refresh_schema",
        ],
    },
    {
        "template_key": CHANGE_SCHEMA_THEN_CREATE_RECORD_TEMPLATE,
        "intent": "change_feishu_schema_then_create_record",
        "risk_level": "write",
        "purpose": "先变更飞书字段结构，刷新 schema 后再新增记录。",
        "step_order": [
            "read_schema",
            "parse_schema_change",
            "validate_schema_change",
            "confirm_schema_change",
            "change_fields",
            "refresh_schema",
            "parse_payload",
            "validate_payload",
            "confirm_write",
            "write_feishu",
        ],
    },
    {
        "template_key": REVIEW_WORKFLOW_MISTAKE_TEMPLATE,
        "intent": "review_workflow_mistake",
        "risk_level": "read",
        "purpose": "复盘对话、失败现象或新需求，生成 Tool、Agent Prompt、Workflow Template、Validator、测试和文档的能力更新建议，不直接改代码或调用有副作用 Tool。",
        "step_order": ["analyze_workflow_mistake"],
    },
]


# 这个函数根据模板 key 生成对应的 workflow plan。
def build_plan_from_template(template_key: str, input_text: str, risk_level: str | None = None) -> dict[str, Any]:
    if template_key == READ_RECORDS_TEMPLATE:
        return _read_plan(input_text)
    if template_key == CREATE_RECORD_TEMPLATE:
        return _write_plan(input_text, CREATE_RECORD_TEMPLATE, "create_feishu_record", "write", CREATE_TOOL, "feishu.create_payload")
    if template_key == UPDATE_RECORD_TEMPLATE:
        return _write_plan(input_text, UPDATE_RECORD_TEMPLATE, "update_feishu_record", "write", UPDATE_TOOL, "feishu.update_payload")
    if template_key == DELETE_RECORD_TEMPLATE:
        return _write_plan(input_text, DELETE_RECORD_TEMPLATE, "delete_feishu_record", "delete", DELETE_TOOL, "feishu.delete_payload")
    if template_key == CHANGE_SCHEMA_TEMPLATE:
        return _schema_change_plan(input_text, risk_level or _schema_risk_level(input_text))
    if template_key == CHANGE_SCHEMA_THEN_CREATE_RECORD_TEMPLATE:
        return _schema_then_create_plan(input_text, risk_level or _schema_risk_level(input_text))
    if template_key == REVIEW_WORKFLOW_MISTAKE_TEMPLATE:
        return _review_workflow_mistake_plan(input_text)
    raise ValueError(f"不支持的 workflow template：{template_key}")


# 这个函数生成读取记录的 plan。
def _read_plan(input_text: str) -> dict[str, Any]:
    read_input = json.dumps(
        {
            "original_input": input_text,
            "read_request": {
                "operation": "search_records",
                "service": "feishu_bitable",
                "field_names": _extract_read_field_names(input_text),
                "filter": {"conjunction": "and", "conditions": _extract_read_conditions(input_text)},
                "sort": [],
                "page_size": 20,
                "automatic_fields": True,
            },
        },
        ensure_ascii=False,
    )
    return {
        "type": "workflow_plan",
        "version": "workflow.v1",
        "template_key": READ_RECORDS_TEMPLATE,
        "intent": "read_feishu_records",
        "risk_level": "read",
        "requires_confirmation": False,
        "original_input": input_text,
        "steps": [
            {
                "step_id": "step_read_records",
                "kind": "tool",
                "tool_name": READ_TOOL,
                "purpose": "读取飞书多维表格记录",
                "input": {"content": [{"text": read_input}]},
                "output": {"save_as": "feishu.records", "content_path": "content[0].text"},
                "validation": {"required": True},
            }
        ],
        "final": {"source": "feishu.records", "format": "answer"},
    }


# 这个函数生成创建、更新、删除类的 plan。
def _write_plan(input_text: str, template_key: str, intent: str, risk_level: str, write_tool: str, payload_key: str) -> dict[str, Any]:
    plan = {
        "type": "workflow_plan",
        "version": "workflow.v1",
        "template_key": template_key,
        "intent": intent,
        "risk_level": risk_level,
        "requires_confirmation": True,
        "original_input": input_text,
        "final": {"source": "write_result", "format": "answer"},
        "steps": [
            _read_schema_step("step_read_schema", "feishu.table_schema", "读取飞书字段定义"),
            _parse_record_payload_step(payload_key, ["feishu.table_schema"]),
        ],
    }
    if write_tool in {UPDATE_TOOL, DELETE_TOOL}:
        plan["steps"].extend(
            [
                _read_candidate_records_step(payload_key),
                _match_record_step(payload_key),
            ]
        )
        validation_inputs = ["feishu.table_schema", payload_key, "feishu.record_match"]
    else:
        validation_inputs = ["feishu.table_schema", payload_key]

    plan["steps"].extend(_record_write_tail(intent, write_tool, validation_inputs))
    return plan


# 这个函数生成字段变更 plan。
def _schema_change_plan(input_text: str, risk_level: str) -> dict[str, Any]:
    return {
        "type": "workflow_plan",
        "version": "workflow.v1",
        "template_key": CHANGE_SCHEMA_TEMPLATE,
        "intent": "change_feishu_schema",
        "risk_level": risk_level,
        "requires_confirmation": True,
        "original_input": input_text,
        "final": {"source": "feishu.schema_change_result", "format": "answer"},
        "steps": [
            _read_schema_step("step_read_schema", "feishu.table_schema", "读取飞书字段定义"),
            _parse_schema_change_step(),
            _schema_change_validation_step(["feishu.table_schema", "feishu.schema_change_payload"]),
            _confirm_step("step_confirm_schema_change", "等待用户确认字段变更", ["validation.schema_change_payload"], "confirmation.schema_change"),
            _change_fields_step(),
            _read_schema_step("step_refresh_schema", "feishu.table_schema_after", "刷新飞书字段定义"),
        ],
    }


# 这个函数生成“先改字段再写记录”的 plan。
def _schema_then_create_plan(input_text: str, risk_level: str) -> dict[str, Any]:
    schema_plan = _schema_change_plan(input_text, risk_level)
    schema_plan["template_key"] = CHANGE_SCHEMA_THEN_CREATE_RECORD_TEMPLATE
    schema_plan["intent"] = "change_feishu_schema_then_create_record"
    schema_plan["final"] = {"source": "write_result", "format": "answer"}
    schema_plan["steps"].extend(
        [
            _parse_record_payload_step("feishu.create_payload", ["feishu.table_schema_after"], step_id="step_parse_payload_after_schema"),
            *_record_write_tail(
                "create_feishu_record",
                CREATE_TOOL,
                ["feishu.table_schema_after", "feishu.create_payload"],
            ),
        ]
    )
    return schema_plan


# 这个函数生成能力复盘 plan；它只产出建议，不直接修改 registry、prompt 或 Tool 代码。
def _review_workflow_mistake_plan(input_text: str) -> dict[str, Any]:
    return {
        "type": "workflow_plan",
        "version": "workflow.v1",
        "template_key": REVIEW_WORKFLOW_MISTAKE_TEMPLATE,
        "intent": "review_workflow_mistake",
        "risk_level": "read",
        "requires_confirmation": False,
        "original_input": input_text,
        "final": {"source": "workflow.capability_update_proposal", "format": "answer"},
        "steps": [
            {
                "step_id": "step_analyze_workflow_mistake",
                "kind": "agent",
                "agent_name": "mistake_agent",
                "prompt_ref": SUMMARIZE_WORKFLOW_MISTAKE_PROMPT,
                "purpose": "总结对话或失败现象，输出能力更新建议",
                "input": {"include_original_input": True},
                "output": {"save_as": "workflow.capability_update_proposal"},
                "validation": {"analysis_only": True},
            }
        ],
    }


# 这个函数生成读取 schema 的步骤。
def _read_schema_step(step_id: str, output_key: str, purpose: str) -> dict[str, Any]:
    return {
        "step_id": step_id,
        "kind": "tool",
        "tool_name": READ_SCHEMA_TOOL,
        "purpose": purpose,
        "input": {"content": [{"text": purpose}]},
        "output": {"save_as": output_key, "content_path": "content[0].text"},
        "validation": {"required": True},
    }


# 这个函数把用户输入解析成写入 payload。
def _parse_record_payload_step(payload_key: str, from_session: list[str], step_id: str = "step_parse_payload") -> dict[str, Any]:
    return {
        "step_id": step_id,
        "kind": "agent",
        "agent_name": "business_agent",
        "prompt_ref": PARSE_FEISHU_RECORD_PROMPT,
        "purpose": "把用户输入转换为飞书写入 payload",
        "input": {"from_session": from_session, "include_original_input": True},
        "output": {"save_as": payload_key},
        "validation": {"reject_unknown_fields": True, "must_match_feishu_schema": True},
    }


# 这个函数把字段变更请求解析成 schema change payload。
def _parse_schema_change_step() -> dict[str, Any]:
    return {
        "step_id": "step_parse_schema_change",
        "kind": "agent",
        "agent_name": "schema_agent",
        "prompt_ref": PARSE_FEISHU_SCHEMA_CHANGE_PROMPT,
        "purpose": "把用户输入转换为飞书字段变更 payload",
        "input": {"from_session": ["feishu.table_schema"], "include_original_input": True},
        "output": {"save_as": "feishu.schema_change_payload"},
        "validation": {"must_match_feishu_schema": True},
    }


# 这个函数生成字段变更校验步骤。
def _schema_change_validation_step(from_session: list[str]) -> dict[str, Any]:
    return {
        "step_id": "step_validate_schema_change",
        "kind": "validation",
        "purpose": "校验字段变更 actions、风险和确认预览",
        "input": {"from_session": from_session},
        "output": {"save_as": "validation.schema_change_payload"},
        "validation": {"operation_intent": "change_feishu_schema", "write_tool": CHANGE_SCHEMA_TOOL},
    }


# 这个函数生成确认步骤。
def _confirm_step(step_id: str, purpose: str, from_session: list[str], output_key: str) -> dict[str, Any]:
    return {
        "step_id": step_id,
        "kind": "confirm",
        "purpose": purpose,
        "input": {"from_session": from_session},
        "output": {"save_as": output_key},
        "validation": {"required": True},
    }


# 这个函数生成执行字段变更的步骤。
def _change_fields_step() -> dict[str, Any]:
    return {
        "step_id": "step_change_fields",
        "kind": "tool",
        "tool_name": CHANGE_SCHEMA_TOOL,
        "purpose": "执行飞书字段变更",
        "input": {"from_session": ["validation.schema_change_payload"]},
        "output": {"save_as": "feishu.schema_change_result", "content_path": "content[0].text"},
        "validation": {"idempotent": True},
    }


# 这个函数生成读取候选记录的步骤。
def _read_candidate_records_step(payload_key: str) -> dict[str, Any]:
    return {
        "step_id": "step_read_candidate_records",
        "kind": "tool",
        "tool_name": READ_TOOL,
        "purpose": "读取候选飞书记录供 search_agent 匹配",
        "input": {
            "from_session": [payload_key],
            "tool_payload_from": {"artifact_key": payload_key, "path": "data_json.candidate_read_payload"},
        },
        "output": {"save_as": "feishu.candidate_records", "content_path": "content[0].text"},
        "validation": {"required": True},
    }


# 这个函数把候选记录匹配到目标 record。
def _match_record_step(payload_key: str) -> dict[str, Any]:
    return {
        "step_id": "step_match_record",
        "kind": "agent",
        "agent_name": "search_agent",
        "prompt_ref": SEARCH_FEISHU_RECORD_PROMPT,
        "purpose": "根据用户输入和候选记录匹配待更新或删除的 record_id",
        "input": {"from_session": [payload_key, "feishu.candidate_records"], "include_original_input": True},
        "output": {"save_as": "feishu.record_match"},
        "validation": {"must_select_candidate_record": True},
    }


# 这个函数补齐写入操作的校验、确认和执行步骤。
def _record_write_tail(intent: str, write_tool: str, validation_inputs: list[str]) -> list[dict[str, Any]]:
    return [
        {
            "step_id": "step_validate_payload",
            "kind": "validation",
            "purpose": "校验写入 payload 字段、匹配记录和定位条件",
            "input": {"from_session": validation_inputs},
            "output": {"save_as": "validation.write_payload"},
            "validation": {"operation_intent": intent, "write_tool": write_tool},
        },
        _confirm_step("step_confirm_write", "等待用户确认写入操作", ["validation.write_payload"], "confirmation.write"),
        {
            "step_id": "step_write_feishu",
            "kind": "tool",
            "tool_name": write_tool,
            "purpose": "执行飞书写入类操作",
            "input": {"from_session": ["validation.write_payload"]},
            "output": {"save_as": "write_result", "content_path": "content[0].text"},
            "validation": {"idempotent": True},
        },
    ]


# 这个函数判断字段变更属于写入还是删除风险。
def _schema_risk_level(input_text: str) -> str:
    return "delete" if _looks_like_field_delete(input_text) else "write"


# 这个函数检查文本里是否有字段删除关键词。
def _looks_like_field_delete(input_text: str) -> bool:
    return "字段" in input_text and any(keyword in input_text for keyword in ("删除", "移除", "清理"))


# 这个函数从查询文本里提取字段名。
def _extract_read_field_names(input_text: str) -> list[str]:
    match = re.search(r"(?:返回|输出|只看|只返回|字段)\s*[:：]?\s*([^，。；;]+(?:[、,，]\s*[^，。；;]+)*)", input_text)
    if not match:
        return []
    fields = [part.strip(" \t\r\n。；;") for part in re.split(r"[、,，\s]+", match.group(1)) if part.strip()]
    return _dedupe(fields)


# 这个函数从查询文本里提取筛选条件。
def _extract_read_conditions(input_text: str) -> list[dict[str, Any]]:
    conditions: list[dict[str, Any]] = []
    status_match = re.search(r"状态(?:为|是|=|：|:)?\s*([^\s，。；;]+)", input_text)
    if status_match:
        conditions.append({"field_name": "状态", "operator": "is", "value": _clean_condition_value(status_match.group(1))})
    else:
        for status in ("进行中", "已完成", "待开始", "未完成"):
            if status in input_text:
                conditions.append({"field_name": "状态", "operator": "is", "value": status})
                break

    priority_match = re.search(r"优先级(?:为|是|=|：|:)?\s*([高中低])", input_text)
    if priority_match:
        conditions.append({"field_name": "优先级", "operator": "is", "value": priority_match.group(1)})
    return conditions


# 这个函数清理条件值。
def _clean_condition_value(value: str) -> str:
    cleaned = value.strip()
    for known in ("进行中", "已完成", "待开始", "未完成"):
        if known in cleaned:
            return known
    return re.sub(r"(的)?记录$", "", cleaned)


# 这个函数去重并保留原有顺序。
def _dedupe(items: list[str]) -> list[str]:
    seen: set[str] = set()
    result: list[str] = []
    for item in items:
        if item not in seen:
            seen.add(item)
            result.append(item)
    return result
