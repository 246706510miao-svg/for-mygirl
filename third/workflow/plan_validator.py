"""workflow_plan 校验器。"""

from __future__ import annotations

from typing import Any

try:
    from ..agents.workflowagent.agent import ALLOWED_TOOLS, WRITE_TOOLS
except ImportError:
    from agents.workflowagent.agent import ALLOWED_TOOLS, WRITE_TOOLS


# 这个异常表示 workflow_plan 不能安全执行。
class PlanValidationError(ValueError):
    pass


# 这个函数校验 workflowagent 输出的计划是否能被 runtime 执行。
def validate_workflow_plan(plan: dict[str, Any]) -> dict[str, Any]:
    if plan.get("type") != "workflow_plan":
        raise PlanValidationError("workflow_plan.type 必须是 workflow_plan。")
    if not isinstance(plan.get("steps"), list) or not plan["steps"]:
        raise PlanValidationError("workflow_plan.steps 必须是非空数组。")

    seen_outputs: set[str] = set()
    seen_kinds: list[str] = []
    write_tool_seen = None
    for index, step in enumerate(plan["steps"], start=1):
        _validate_step(index, step, seen_outputs)
        seen_kinds.append(str(step.get("kind")))
        tool_name = step.get("tool_name")
        if tool_name in WRITE_TOOLS:
            write_tool_seen = tool_name
        output = step.get("output")
        if isinstance(output, dict) and output.get("save_as"):
            seen_outputs.add(str(output["save_as"]))

    if write_tool_seen:
        _validate_write_plan(plan, seen_kinds)
    return plan


# 这个函数校验单个步骤的基本结构。
def _validate_step(index: int, step: dict[str, Any], seen_outputs: set[str]) -> None:
    if not isinstance(step, dict):
        raise PlanValidationError(f"第 {index} 个 step 不是对象。")
    step_kind = str(step.get("kind") or "")
    if step_kind not in {"tool", "agent", "validation", "confirm"}:
        raise PlanValidationError(f"第 {index} 个 step.kind 不受支持：{step_kind}")
    if step_kind == "tool" and step.get("tool_name") not in ALLOWED_TOOLS:
        raise PlanValidationError(f"第 {index} 个 step.tool_name 不受支持：{step.get('tool_name')}")

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
