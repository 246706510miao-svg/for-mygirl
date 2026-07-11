"""策划 LLM 可选择的第一版原子动作目录。"""

from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any


@dataclass(frozen=True, slots=True)
class ActionDefinition:
    action_name: str
    kind: str
    description: str
    input_contract: dict[str, Any]
    produces: str
    external_side_effect: bool = False
    requires_confirmation: bool = False

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


_DEFINITIONS = [
    ActionDefinition(
        "generate_record_draft",
        "prepare",
        "把业务对话整理成 Spring Boot 可消费的记录草稿。",
        {},
        "record_draft",
    ),
    ActionDefinition("read_table_schema", "tool", "读取当前飞书表字段定义。", {}, "table_schema"),
    ActionDefinition(
        "read_records",
        "tool",
        "按条件读取候选记录；没有结果时返回 no_match，而不是终止任务。",
        {"read_request": "可选；飞书读取请求对象"},
        "candidate_records",
    ),
    ActionDefinition(
        "prepare_create_record",
        "prepare",
        "把用户目标整理成新增记录候选 payload。",
        {"fields": "字段名到值的对象；可选，缺省时使用规则兜底解析"},
        "prepared_operation",
    ),
    ActionDefinition(
        "prepare_update_record",
        "prepare",
        "整理更新字段和待匹配记录的粗定位条件。",
        {"fields": "更新字段", "lookup": "可选粗定位条件", "record_id": "可选"},
        "prepared_operation",
    ),
    ActionDefinition(
        "prepare_delete_record",
        "prepare",
        "整理删除目标的 record_id 或粗定位条件。",
        {"lookup": "可选粗定位条件", "record_id": "可选"},
        "prepared_operation",
    ),
    ActionDefinition(
        "prepare_schema_change",
        "prepare",
        "整理字段新增、重命名或删除 actions；信息不足时返回 needs_input。",
        {"actions": "字段变更 action 数组"},
        "prepared_operation",
    ),
    ActionDefinition(
        "match_record",
        "prepare",
        "从 read_records 的候选中选择唯一 record_id；不确定时回到用户选择。",
        {"record_id": "可选；必须来自候选记录"},
        "selected_record",
    ),
    ActionDefinition(
        "ask_user",
        "interaction",
        "向用户追问缺失信息或要求用户选择候选。",
        {"question": "问题", "options": "可选候选数组", "kind": "clarify 或 choose_candidate"},
        "user_event",
    ),
    ActionDefinition("create_record", "tool", "执行新增记录。", {}, "write_result", True, True),
    ActionDefinition("update_record", "tool", "执行更新记录。", {}, "write_result", True, True),
    ActionDefinition("delete_record", "tool", "执行删除记录。", {}, "write_result", True, True),
    ActionDefinition("change_fields", "tool", "执行字段结构变更。", {}, "schema_change_result", True, True),
    ActionDefinition(
        "finish",
        "output",
        "任务目标完成或只能给出说明时，向用户输出最终回答并结束。",
        {"content": "最终回答"},
        "final_answer",
    ),
]

ACTION_CATALOG = {definition.action_name: definition for definition in _DEFINITIONS}
WRITE_ACTIONS = {name for name, definition in ACTION_CATALOG.items() if definition.external_side_effect}


def catalog_for_planner() -> list[dict[str, Any]]:
    return [definition.to_dict() for definition in _DEFINITIONS]


def get_action_definition(action_name: str) -> ActionDefinition:
    definition = ACTION_CATALOG.get(action_name)
    if not definition:
        raise ValueError(f"策划选择了未注册动作：{action_name}")
    return definition
