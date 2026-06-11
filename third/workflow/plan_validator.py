"""workflow_plan 校验器。"""

from __future__ import annotations

from copy import deepcopy
from typing import Any

try:
    from ..agents.workflowagent.agent import ALLOWED_TOOLS, WRITE_TOOLS
except ImportError:
    from agents.workflowagent.agent import ALLOWED_TOOLS, WRITE_TOOLS


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
    for index, step in enumerate(plan["steps"], start=1):
        _validate_step(index, step, seen_outputs, agent_catalog)
        seen_kinds.append(str(step.get("kind")))
        tool_name = step.get("tool_name")
        if tool_name in WRITE_TOOLS:
            write_tool_seen = tool_name
        output = step.get("output")
        if isinstance(output, dict) and output.get("save_as"):
            seen_outputs.add(str(output["save_as"]))

    if write_tool_seen:
        _validate_write_plan(plan, seen_kinds)
    _normalize_final(plan, write_tool_seen)
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
def _normalize_final(plan: dict[str, Any], write_tool_seen: str | None) -> None:
    final = plan.get("final")
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


# 这个函数识别用户原文里明确要求写入飞书的表达。
def _looks_like_write_to_feishu(value: Any) -> bool:
    text = str(value or "")
    if not any(target in text for target in ("飞书", "多维表格", "表格")):
        return False
    return any(
        keyword in text
        for keyword in ("写入", "写到", "写进", "保存到", "存到", "同步到", "记录到", "记到", "填到", "新增到", "添加到")
    )


# 这个函数把启用的 Agent 提示词目录转换为 prompt_ref 到 agent_name 的索引。
def _agent_catalog(agent_prompts: list[dict[str, Any]] | None) -> dict[str, str] | None:
    if agent_prompts is None:
        return None
    return {
        str(prompt.get("prompt_key")): str(prompt.get("agent_name"))
        for prompt in agent_prompts
        if prompt.get("enabled", True) and prompt.get("prompt_key") and prompt.get("agent_name")
    }
