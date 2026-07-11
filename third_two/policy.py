"""稳定业务契约所需的最小强制决策，不承担通用任务规划。"""

from __future__ import annotations

from typing import Any

from .contracts import ActionDecision, TaskState


def required_business_decision(state: TaskState, artifacts: dict[str, Any]) -> ActionDecision | None:
    """让后端声明的确定性操作优先于自然语言猜测。"""

    context = state.goal.get("business_context") if isinstance(state.goal, dict) else None
    operation = str((context or {}).get("operation") or "") if isinstance(context, dict) else ""
    if operation != "draft_generate":
        return None
    draft = artifacts.get("record_draft")
    if not isinstance(draft, dict):
        return ActionDecision(
            action_name="generate_record_draft",
            expected_outcome="生成后端可消费的 record_draft Artifact",
            decision_summary="业务 metadata 明确要求只生成草稿。",
        )
    return ActionDecision(
        action_name="finish",
        arguments={"content": str(draft.get("previewText") or "记录草稿已生成。")},
        expected_outcome="返回草稿生成结果",
        decision_summary="record_draft 已生成，结束当前任务。",
    )
