"""将 ActionDecision 和 Observation 归约进结构化 TaskState。"""

from __future__ import annotations

from typing import Any

from .contracts import ActionDecision, Observation, TaskState


class TaskStateReducer:
    def apply(self, state: TaskState, decision: ActionDecision, observation: Observation) -> TaskState:
        self._apply_user_state_patch(state, decision.state_patch)
        state.last_decision = decision.to_dict()
        state.last_observation = {
            "action_id": observation.action_id,
            "action_name": observation.action_name,
            "status": observation.status,
            "summary": observation.summary,
            "artifact_ref": observation.artifact_ref,
            "error_code": observation.error_code,
            "recoverable": observation.recoverable,
            "created_at": observation.created_at,
        }
        state.step_count += 1
        state.decision_signatures.append(decision.signature())
        state.completed_actions.append(
            {
                "action_id": decision.action_id,
                "action_name": decision.action_name,
                "status": observation.status,
                "decision_summary": decision.decision_summary,
                "expected_outcome": decision.expected_outcome,
                "observation_summary": observation.summary,
                "artifact_ref": observation.artifact_ref,
                "error_code": observation.error_code,
                "created_at": observation.created_at,
            }
        )
        state.facts.update(observation.fact_patch)
        state.pending_decision = None

        if observation.status == "terminal_error":
            state.status = "failed"
            state.error_text = observation.summary or observation.error_code or "动作执行失败。"
        elif observation.status == "retryable_error":
            count = int(state.retry_counts.get(decision.action_name) or 0) + 1
            state.retry_counts[decision.action_name] = count
            if count >= 3:
                state.status = "failed"
                state.error_text = observation.summary or "动作连续重试失败。"
            else:
                state.status = "running"
        else:
            state.status = "running"

        if state.step_count >= state.max_steps and state.status == "running":
            state.status = "failed"
            state.error_text = f"任务执行达到最大动作数：{state.max_steps}。"
        return state

    def _apply_user_state_patch(self, state: TaskState, patch: dict[str, Any]) -> None:
        """策划只能更新用户任务语义，不能覆盖运行状态和安全字段。"""

        if not isinstance(patch, dict):
            return
        known_slots = patch.get("known_slots") or patch.get("knownSlots")
        if isinstance(known_slots, dict):
            state.known_slots.update(known_slots)
        missing_slots = patch.get("missing_slots") or patch.get("missingSlots")
        if isinstance(missing_slots, list):
            state.missing_slots = [str(item) for item in missing_slots if str(item).strip()]
        goal = patch.get("goal")
        if isinstance(goal, dict):
            if goal.get("summary"):
                state.goal["summary"] = str(goal["summary"])
            if isinstance(goal.get("success_criteria"), list):
                state.goal["success_criteria"] = [str(item) for item in goal["success_criteria"]]
