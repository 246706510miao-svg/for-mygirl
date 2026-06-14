"""workflow_plan 校验器。"""

from __future__ import annotations

from copy import deepcopy
from typing import Any

try:
    from .registry import ALLOWED_TOOLS, CHANGE_SCHEMA_TOOL, DELETE_TOOL, READ_SCHEMA_TOOL, READ_TOOL, TEMPLATE_CATALOG, UPDATE_TOOL, WRITE_TOOLS
except ImportError:
    from workflow.registry import ALLOWED_TOOLS, CHANGE_SCHEMA_TOOL, DELETE_TOOL, READ_SCHEMA_TOOL, READ_TOOL, TEMPLATE_CATALOG, UPDATE_TOOL, WRITE_TOOLS


# 这个异常表示 workflow_plan 不能安全执行。
class PlanValidationError(ValueError):
    pass


# 这个函数校验 workflowagent 输出的计划是否能被 runtime 执行。
def validate_workflow_plan(plan: dict[str, Any], agent_prompts: list[dict[str, Any]] | None = None) -> dict[str, Any]:
    plan = _normalize_plan(plan)
    if plan.get("type") != "workflow_plan":
        raise PlanValidationError("workflow_plan.type 必须是 workflow_plan。")
    if not isinstance(plan.get("steps"), list) or not plan["steps"]:
        raise PlanValidationError("workflow_plan.steps 必须是非空数组。")
    if plan.get("intent") == "read_feishu_records" and _looks_like_write_to_feishu(plan.get("original_input")):
        raise PlanValidationError("workflow_plan 把明显写入飞书的请求规划成读取，请改用 create/update/delete 写入链路。")

    agent_catalog = _agent_catalog(agent_prompts)
    seen_outputs: set[str] = set()
    seen_kinds: list[str] = []
    write_tool_seen = None
    write_tools_seen: set[str] = set()
    steps = plan["steps"]
    for index, step in enumerate(plan["steps"], start=1):
        _validate_step(index, step, seen_outputs, agent_catalog)
        seen_kinds.append(str(step.get("kind")))
        tool_name = step.get("tool_name")
        if tool_name in WRITE_TOOLS:
            write_tool_seen = tool_name
            write_tools_seen.add(str(tool_name))
        output = step.get("output")
        if isinstance(output, dict) and output.get("save_as"):
            seen_outputs.add(str(output["save_as"]))

    _validate_template_key(plan)
    if write_tools_seen:
        _validate_write_plan(plan, seen_kinds)
        _normalize_write_validation_artifact(plan)
    if write_tools_seen.intersection({UPDATE_TOOL, DELETE_TOOL}):
        _validate_update_delete_match_flow(steps)
    if CHANGE_SCHEMA_TOOL in write_tools_seen:
        _validate_schema_change_flow(plan, steps)
    _normalize_final(plan, write_tool_seen, write_tools_seen)
    return plan


# 这个函数兼容 LLM 常见字段别名，但不会替模型补业务决策。
def _normalize_plan(plan: dict[str, Any]) -> dict[str, Any]:
    normalized = deepcopy(plan)
    for step in normalized.get("steps") or []:
        if not isinstance(step, dict):
            continue
        if "input" not in step and isinstance(step.get("input_spec"), dict):
            step["input"] = step["input_spec"]
        if "output" not in step and step.get("output_key"):
            step["output"] = {"save_as": step["output_key"]}
        if str(step.get("kind") or "") == "tool" and not step.get("tool_name"):
            alias = step.get("name") or step.get("tool") or step.get("toolName")
            if alias in ALLOWED_TOOLS:
                step["tool_name"] = alias
    return normalized


# 这个函数把 LLM 常见的 final 字符串输出归一成 runtime 可读取的结构。
def _normalize_final(plan: dict[str, Any], write_tool_seen: str | None, write_tools_seen: set[str] | None = None) -> None:
    final = plan.get("final")
    if write_tools_seen == {CHANGE_SCHEMA_TOOL}:
        default_source = "feishu.schema_change_result"
    else:
        default_source = "write_result" if write_tool_seen else "feishu.records"
    if not isinstance(final, dict):
        plan["final"] = {"source": default_source, "format": "answer"}
        return
    if not final.get("source"):
        final["source"] = default_source
    if not final.get("format"):
        final["format"] = "answer"


# 这个函数校验单个步骤的基本结构。
def _validate_step(index: int, step: dict[str, Any], seen_outputs: set[str], agent_catalog: dict[str, str] | None) -> None:
    if not isinstance(step, dict):
        raise PlanValidationError(f"第 {index} 个 step 不是对象。")
    step_kind = str(step.get("kind") or "")
    if step_kind not in {"tool", "agent", "validation", "confirm"}:
        raise PlanValidationError(f"第 {index} 个 step.kind 不受支持：{step_kind}")
    if step_kind == "tool" and step.get("tool_name") not in ALLOWED_TOOLS:
        raise PlanValidationError(f"第 {index} 个 step.tool_name 不受支持：{step.get('tool_name')}")
    if step_kind == "agent" and agent_catalog is not None:
        prompt_ref = str(step.get("prompt_ref") or "")
        agent_name = str(step.get("agent_name") or "")
        expected_agent = agent_catalog.get(prompt_ref)
        if not expected_agent:
            raise PlanValidationError(f"第 {index} 个 step.prompt_ref 未注册或未启用：{prompt_ref}")
        if agent_name != expected_agent:
            raise PlanValidationError(f"第 {index} 个 step.agent_name 与 prompt_ref 不匹配：{agent_name} != {expected_agent}")

    input_spec = step.get("input") or {}
    if isinstance(input_spec, dict):
        for artifact_key in input_spec.get("from_session") or []:
            if artifact_key not in seen_outputs:
                raise PlanValidationError(f"第 {index} 个 step 依赖尚未产生的 artifact：{artifact_key}")


# 这个函数校验写入类计划的必要安全步骤。
def _validate_write_plan(plan: dict[str, Any], step_kinds: list[str]) -> None:
    if not plan.get("requires_confirmation"):
        raise PlanValidationError("写入类 workflow_plan 必须 requires_confirmation=true。")
    for required_kind in ("agent", "validation", "confirm"):
        if required_kind not in step_kinds:
            raise PlanValidationError(f"写入类 workflow_plan 缺少 {required_kind} 步骤。")


def _validate_template_key(plan: dict[str, Any]) -> None:
    template_key = plan.get("template_key")
    if not template_key:
        return
    allowed_templates = {str(item.get("template_key")) for item in TEMPLATE_CATALOG}
    if str(template_key) not in allowed_templates:
        raise PlanValidationError(f"workflow_plan.template_key 不受支持：{template_key}")


def _normalize_write_validation_artifact(plan: dict[str, Any]) -> None:
    validation_keys: list[str] = []
    for step in plan.get("steps") or []:
        if step.get("kind") != "validation":
            continue
        output = step.get("output") if isinstance(step.get("output"), dict) else {}
        save_as = str(output.get("save_as") or "")
        if save_as == "validation.schema_change_payload":
            continue
        if save_as.startswith("validation.") and save_as != "validation.write_payload":
            validation_keys.append(save_as)
            output["save_as"] = "validation.write_payload"
            step["output"] = output
    if not validation_keys:
        return
    replacements = set(validation_keys)
    for step in plan.get("steps") or []:
        input_spec = step.get("input")
        if not isinstance(input_spec, dict):
            continue
        from_session = input_spec.get("from_session")
        if not isinstance(from_session, list):
            continue
        input_spec["from_session"] = [
            "validation.write_payload" if str(artifact_key) in replacements else artifact_key for artifact_key in from_session
        ]


def _validate_update_delete_match_flow(steps: list[dict[str, Any]]) -> None:
    has_candidate_read = any(
        step.get("kind") == "tool"
        and step.get("tool_name") == READ_TOOL
        and isinstance(step.get("output"), dict)
        and step["output"].get("save_as") == "feishu.candidate_records"
        for step in steps
    )
    has_record_match = any(
        step.get("kind") == "agent"
        and step.get("prompt_ref") == "search_feishu_record.v1"
        and isinstance(step.get("output"), dict)
        and step["output"].get("save_as") == "feishu.record_match"
        for step in steps
    )
    validation_uses_match = any(
        step.get("kind") == "validation"
        and "feishu.record_match" in ((step.get("input") or {}).get("from_session") or [])
        for step in steps
    )
    if not has_candidate_read:
        raise PlanValidationError("更新或删除 workflow_plan 必须先读取 feishu.candidate_records。")
    if not has_record_match:
        raise PlanValidationError("更新或删除 workflow_plan 必须使用 search_feishu_record.v1 生成 feishu.record_match。")
    if not validation_uses_match:
        raise PlanValidationError("更新或删除 workflow_plan 的 validation 必须依赖 feishu.record_match。")


def _validate_schema_change_flow(plan: dict[str, Any], steps: list[dict[str, Any]]) -> None:
    required = {
        "schema_payload": _step_index(
            steps,
            lambda step: step.get("kind") == "agent"
            and step.get("prompt_ref") == "parse_feishu_schema_change.v1"
            and isinstance(step.get("output"), dict)
            and step["output"].get("save_as") == "feishu.schema_change_payload",
        ),
        "schema_validation": _step_index(
            steps,
            lambda step: step.get("kind") == "validation"
            and isinstance(step.get("output"), dict)
            and step["output"].get("save_as") == "validation.schema_change_payload",
        ),
        "schema_confirm": _step_index(
            steps,
            lambda step: step.get("kind") == "confirm"
            and "validation.schema_change_payload" in ((step.get("input") or {}).get("from_session") or []),
        ),
        "change_tool": _step_index(
            steps,
            lambda step: step.get("kind") == "tool"
            and step.get("tool_name") == CHANGE_SCHEMA_TOOL
            and "validation.schema_change_payload" in ((step.get("input") or {}).get("from_session") or []),
        ),
        "refresh_schema": _step_index(
            steps,
            lambda step: step.get("kind") == "tool"
            and step.get("tool_name") == READ_SCHEMA_TOOL
            and isinstance(step.get("output"), dict)
            and step["output"].get("save_as") == "feishu.table_schema_after",
        ),
    }
    missing = [key for key, index in required.items() if index < 0]
    if missing:
        raise PlanValidationError(f"字段变更 workflow_plan 缺少必要步骤：{', '.join(missing)}")
    ordered = [required["schema_payload"], required["schema_validation"], required["schema_confirm"], required["change_tool"], required["refresh_schema"]]
    if ordered != sorted(ordered):
        raise PlanValidationError("字段变更 workflow_plan 步骤顺序必须是 parse -> validation -> confirm -> change_fields -> refresh_schema。")
    if _looks_like_field_delete(plan.get("original_input")) and plan.get("risk_level") != "delete":
        raise PlanValidationError("删除字段 workflow_plan 必须 risk_level=delete。")
    record_parse_after_refresh = _step_index(
        steps,
        lambda step: step.get("kind") == "agent"
        and step.get("prompt_ref") == "parse_feishu_record.v1"
        and "feishu.table_schema_after" in ((step.get("input") or {}).get("from_session") or []),
    )
    if plan.get("template_key") == "change_schema_then_create_record" and record_parse_after_refresh < 0:
        raise PlanValidationError("字段变更后写记录 workflow_plan 必须使用 feishu.table_schema_after 解析记录 payload。")
    if record_parse_after_refresh >= 0 and record_parse_after_refresh < required["refresh_schema"]:
        raise PlanValidationError("字段变更后写记录必须先刷新 feishu.table_schema_after。")


def _step_index(steps: list[dict[str, Any]], predicate: Any) -> int:
    for index, step in enumerate(steps):
        if predicate(step):
            return index
    return -1


# 这个函数识别用户原文里明确要求写入飞书的表达。
def _looks_like_write_to_feishu(value: Any) -> bool:
    text = str(value or "")
    if not any(target in text for target in ("飞书", "多维表格", "表格")):
        return False
    return any(
        keyword in text
        for keyword in ("写入", "写到", "写进", "保存到", "存到", "同步到", "记录到", "记到", "填到", "新增到", "添加到")
    )


def _looks_like_field_delete(value: Any) -> bool:
    text = str(value or "")
    return "字段" in text and any(keyword in text for keyword in ("删除", "移除", "清理"))


# 这个函数把启用的 Agent 提示词目录转换为 prompt_ref 到 agent_name 的索引。
def _agent_catalog(agent_prompts: list[dict[str, Any]] | None) -> dict[str, str] | None:
    if agent_prompts is None:
        return None
    return {
        str(prompt.get("prompt_key")): str(prompt.get("agent_name"))
        for prompt in agent_prompts
        if prompt.get("enabled", True) and prompt.get("prompt_key") and prompt.get("agent_name")
    }
