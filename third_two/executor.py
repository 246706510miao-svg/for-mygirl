"""third_two 滚动策划执行器：每次只执行一个动作并把结果回流。"""

from __future__ import annotations

import hashlib
import json
from typing import Any

from .action_catalog import WRITE_ACTIONS, get_action_definition
from .actions import ActionDispatcher
from .contracts import ActionDecision, InteractionRequest, Observation, TaskState, now_iso
from .planner import Planner, create_default_planner
from .policy import required_business_decision
from .reducer import TaskStateReducer
from .repository import InMemoryTaskRepository


_ARTIFACT_FACT_KEYS = {
    "table_schema": "table_schema_ref",
    "candidate_records": "candidate_records_ref",
    "prepared_operation": "prepared_operation_ref",
    "selected_record": "selected_record_ref",
    "write_result": "write_result_ref",
    "schema_change_result": "schema_change_result_ref",
}


class RollingTaskExecutor:
    def __init__(
        self,
        repository: InMemoryTaskRepository | None = None,
        planner: Planner | None = None,
        dispatcher: ActionDispatcher | None = None,
        reducer: TaskStateReducer | None = None,
        repeat_limit: int = 3,
    ) -> None:
        self.repository = repository or InMemoryTaskRepository()
        self.planner = planner or create_default_planner()
        self.dispatcher = dispatcher or ActionDispatcher()
        self.reducer = reducer or TaskStateReducer()
        self.repeat_limit = max(2, repeat_limit)

    def create_task(
        self,
        original_input: str,
        goal: dict[str, Any] | None = None,
        private_metadata: dict[str, Any] | None = None,
        max_steps: int = 20,
    ) -> TaskState:
        return self.repository.create_task(
            original_input,
            goal=goal,
            private_metadata=private_metadata,
            max_steps=max_steps,
        )

    def run_until_boundary(self, task_id: str) -> TaskState:
        state = self._require_task(task_id)
        while state.status == "running":
            if state.step_count >= state.max_steps:
                state.status = "failed"
                state.error_text = f"任务执行达到最大动作数：{state.max_steps}。"
                return self.repository.save_task(state)
            try:
                decision = self._next_decision(state)
                definition = get_action_definition(decision.action_name)
            except Exception as exc:
                state.status = "failed"
                state.error_text = str(exc)
                return self.repository.save_task(state)

            if self._is_repeating(state, decision):
                state.status = "failed"
                state.error_text = f"策划连续选择相同动作，已停止：{decision.action_name}。"
                return self.repository.save_task(state)

            if definition.kind == "interaction":
                return self._wait_for_user(state, decision)
            if definition.kind == "output":
                return self._finish(state, decision)

            execution_hash = self._execution_hash(state, decision)
            if decision.action_name in WRITE_ACTIONS:
                precondition_error = self._write_precondition_error(state, decision)
                if precondition_error:
                    observation = Observation(
                        action_id=decision.action_id,
                        action_name=decision.action_name,
                        status="needs_input",
                        summary=precondition_error,
                        error_code="write_precondition_missing",
                    )
                    state = self.reducer.apply(state, decision, observation)
                    state = self.repository.save_task(state)
                    continue
                if execution_hash in state.executed_action_hashes:
                    observation = Observation(
                        action_id=decision.action_id,
                        action_name=decision.action_name,
                        status="success",
                        summary="相同写入动作已经成功执行，本次按幂等规则跳过。",
                        data={"idempotent": True, "execution_hash": execution_hash},
                    )
                    state = self.reducer.apply(state, decision, observation)
                    state = self.repository.save_task(state)
                    continue
                if execution_hash not in state.approved_action_hashes:
                    return self._wait_for_confirmation(state, decision, execution_hash)

            try:
                observation = self.dispatcher.dispatch(decision, state, self.repository)
            except Exception as exc:
                observation = Observation(
                    action_id=decision.action_id,
                    action_name=decision.action_name,
                    status="terminal_error",
                    summary=f"动作执行器异常：{exc}",
                    error_code="action_dispatch_error",
                    recoverable=False,
                )
            self._persist_observation(state, observation)
            if decision.action_name in WRITE_ACTIONS and observation.status == "success":
                state.executed_action_hashes.append(execution_hash)
                state.approved_action_hashes = [item for item in state.approved_action_hashes if item != execution_hash]
            state = self.reducer.apply(state, decision, observation)
            state = self.repository.save_task(state)
        return state

    def resume(self, task_id: str, interaction_id: str, response: str, content: str = "") -> TaskState:
        state = self._require_task(task_id)
        interaction = state.pending_interaction or {}
        if state.status != "waiting_user" or interaction.get("interaction_id") != interaction_id:
            raise ValueError("当前任务没有对应的待处理用户交互。")
        normalized = response.strip().lower()
        if normalized in {"cancel", "cancelled", "取消", "reject", "rejected"}:
            state.status = "cancelled"
            state.final_answer = "已取消本次任务。"
            state.pending_interaction = None
            state.pending_decision = None
            return self.repository.save_task(state)

        if interaction.get("kind") == "confirm":
            if normalized in {"approve", "approved", "confirm", "确认", "同意"}:
                decision_hash = str(interaction.get("decision_hash") or "")
                if not decision_hash:
                    raise ValueError("确认请求缺少 decision_hash。")
                state.approved_action_hashes.append(decision_hash)
                state.pending_interaction = None
                state.status = "running"
                state.user_events.append(
                    {"event_type": "user_confirmation", "content": content or "确认", "created_at": now_iso()}
                )
                state = self.repository.save_task(state)
                return self.run_until_boundary(state.task_id)
            if normalized in {"modify", "修改", "change"}:
                if not content.strip():
                    raise ValueError("修改确认内容时需要提供新的用户说明。")
                state.pending_interaction = None
                state.pending_decision = None
                state.status = "running"
                state.user_events.append(
                    {"event_type": "user_modification", "content": content.strip(), "created_at": now_iso()}
                )
                state = self.repository.save_task(state)
                return self.run_until_boundary(state.task_id)
            raise ValueError("确认交互只支持 approve、modify 或 cancel。")

        if not content.strip():
            raise ValueError("回答追问或选择候选时需要提供 content。")
        state.pending_interaction = None
        state.pending_decision = None
        state.status = "running"
        state.user_events.append(
            {"event_type": "user_reply", "content": content.strip(), "created_at": now_iso()}
        )
        state = self.repository.save_task(state)
        return self.run_until_boundary(state.task_id)

    def _next_decision(self, state: TaskState) -> ActionDecision:
        if state.pending_decision:
            return ActionDecision.from_dict(state.pending_decision)
        artifacts = self.repository.planner_artifacts(state.task_id)
        required = required_business_decision(state, artifacts)
        if required:
            return required
        return self.planner.decide(state, artifacts)

    def _wait_for_user(self, state: TaskState, decision: ActionDecision) -> TaskState:
        question = str(decision.arguments.get("question") or "请补充完成任务所需的信息。")
        options = decision.arguments.get("options") if isinstance(decision.arguments.get("options"), list) else []
        requested_kind = str(decision.arguments.get("kind") or "clarify")
        kind = "choose_candidate" if requested_kind == "choose_candidate" else "clarify"
        observation = Observation(
            action_id=decision.action_id,
            action_name=decision.action_name,
            status="needs_input",
            summary=question,
            data={"question": question, "options": options},
            error_code="user_input_required",
        )
        state = self.reducer.apply(state, decision, observation)
        interaction = InteractionRequest(kind=kind, question=question, options=options)
        state.pending_interaction = interaction.to_dict()
        state.status = "waiting_user"
        return self.repository.save_task(state)

    def _wait_for_confirmation(self, state: TaskState, decision: ActionDecision, execution_hash: str) -> TaskState:
        prepared = self.repository.get_latest_artifact(state.task_id, "prepared_operation")
        preview = (prepared or {}).get("data") or {"action_name": decision.action_name, "arguments": decision.arguments}
        interaction = InteractionRequest(
            kind="confirm",
            question=_confirmation_question(decision.action_name),
            options=["approve", "modify", "cancel"],
            pending_decision=decision.to_dict(),
            decision_hash=execution_hash,
        )
        state.last_decision = decision.to_dict()
        state.pending_decision = decision.to_dict()
        state.pending_interaction = {**interaction.to_dict(), "preview": preview}
        state.status = "waiting_user"
        return self.repository.save_task(state)

    def _finish(self, state: TaskState, decision: ActionDecision) -> TaskState:
        content = str(decision.arguments.get("content") or decision.arguments.get("answer") or "任务已完成。")
        observation = Observation(
            action_id=decision.action_id,
            action_name=decision.action_name,
            status="success",
            summary=content,
            data={"answer": content},
            artifact_key="final_answer",
        )
        self._persist_observation(state, observation)
        state = self.reducer.apply(state, decision, observation)
        state.status = "completed"
        state.final_answer = content
        state.error_text = None
        return self.repository.save_task(state)

    def _persist_observation(self, state: TaskState, observation: Observation) -> None:
        if not observation.artifact_key:
            return
        artifact = self.repository.save_artifact(state.task_id, observation.artifact_key, observation.data)
        observation.artifact_ref = str(artifact["artifact_id"])
        fact_key = _ARTIFACT_FACT_KEYS.get(observation.artifact_key)
        if fact_key:
            observation.fact_patch[fact_key] = observation.artifact_ref

    def _execution_hash(self, state: TaskState, decision: ActionDecision) -> str:
        prepared = self.repository.get_latest_artifact(state.task_id, "prepared_operation")
        payload = {
            "task_id": state.task_id,
            "action_name": decision.action_name,
            "arguments": decision.arguments,
            "prepared_operation": (prepared or {}).get("data"),
        }
        canonical = json.dumps(payload, ensure_ascii=False, sort_keys=True, default=str)
        return hashlib.sha256(canonical.encode("utf-8")).hexdigest()

    def _write_precondition_error(self, state: TaskState, decision: ActionDecision) -> str | None:
        prepared = self.repository.get_latest_artifact(state.task_id, "prepared_operation")
        prepared_data = (prepared or {}).get("data") or {}
        expected_operation = {
            "create_record": "create_record",
            "update_record": "update_record",
            "delete_record": "delete_record",
            "change_fields": "change_fields",
        }[decision.action_name]
        if prepared_data.get("operation") != expected_operation:
            return f"执行 {decision.action_name} 前必须先生成对应的 prepared_operation。"
        request = prepared_data.get("request") if isinstance(prepared_data.get("request"), dict) else {}
        if decision.action_name in {"update_record", "delete_record"}:
            if not request.get("record_id") and not state.facts.get("selected_record_id"):
                return f"执行 {decision.action_name} 前必须先通过 match_record 确定唯一 record_id。"
        return None

    def _is_repeating(self, state: TaskState, decision: ActionDecision) -> bool:
        signature = decision.signature()
        if len(state.decision_signatures) < self.repeat_limit - 1:
            return False
        return all(item == signature for item in state.decision_signatures[-(self.repeat_limit - 1):])

    def _require_task(self, task_id: str) -> TaskState:
        state = self.repository.get_task(task_id)
        if not state:
            raise KeyError(f"third_two task 不存在：{task_id}")
        return state


def _confirmation_question(action_name: str) -> str:
    labels = {
        "create_record": "新增飞书记录",
        "update_record": "更新飞书记录",
        "delete_record": "删除飞书记录",
        "change_fields": "修改飞书字段",
    }
    return f"确认执行“{labels.get(action_name, action_name)}”吗？你可以确认、修改或取消。"
