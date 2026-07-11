"""third_two 的结构化任务、动作决策、观察结果和用户交互契约。"""

from __future__ import annotations

import hashlib
import json
from copy import deepcopy
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from typing import Any
from uuid import uuid4


TASK_STATUSES = {"running", "waiting_user", "completed", "failed", "cancelled"}
OBSERVATION_STATUSES = {
    "success",
    "no_match",
    "needs_input",
    "conflict",
    "retryable_error",
    "terminal_error",
}
INTERACTION_KINDS = {"clarify", "confirm", "choose_candidate"}


def new_id(prefix: str) -> str:
    return f"{prefix}_{uuid4().hex[:24]}"


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


@dataclass(slots=True)
class ActionDecision:
    """策划 LLM 每一轮只能输出一个可执行动作。"""

    action_name: str
    arguments: dict[str, Any] = field(default_factory=dict)
    expected_outcome: str = ""
    decision_summary: str = ""
    state_patch: dict[str, Any] = field(default_factory=dict)
    action_id: str = field(default_factory=lambda: new_id("action"))

    def signature(self) -> str:
        canonical = json.dumps(
            {"action_name": self.action_name, "arguments": self.arguments},
            ensure_ascii=False,
            sort_keys=True,
            default=str,
        )
        return hashlib.sha256(canonical.encode("utf-8")).hexdigest()

    def to_dict(self) -> dict[str, Any]:
        return deepcopy(asdict(self))

    @classmethod
    def from_dict(cls, value: dict[str, Any]) -> "ActionDecision":
        action_name = str(value.get("action_name") or value.get("actionName") or "").strip()
        if not action_name:
            raise ValueError("ActionDecision.action_name 不能为空。")
        arguments = value.get("arguments") if isinstance(value.get("arguments"), dict) else {}
        state_patch = value.get("state_patch") or value.get("statePatch") or {}
        return cls(
            action_id=str(value.get("action_id") or value.get("actionId") or new_id("action")),
            action_name=action_name,
            arguments=deepcopy(arguments),
            expected_outcome=str(value.get("expected_outcome") or value.get("expectedOutcome") or ""),
            decision_summary=str(value.get("decision_summary") or value.get("decisionSummary") or ""),
            state_patch=deepcopy(state_patch) if isinstance(state_patch, dict) else {},
        )


@dataclass(slots=True)
class Observation:
    """一个原子动作执行后的统一回流对象。"""

    action_id: str
    action_name: str
    status: str
    summary: str = ""
    data: dict[str, Any] = field(default_factory=dict)
    fact_patch: dict[str, Any] = field(default_factory=dict)
    artifact_key: str | None = None
    artifact_ref: str | None = None
    error_code: str | None = None
    recoverable: bool = True
    created_at: str = field(default_factory=now_iso)

    def __post_init__(self) -> None:
        if self.status not in OBSERVATION_STATUSES:
            raise ValueError(f"不支持的 Observation.status：{self.status}")

    def to_dict(self) -> dict[str, Any]:
        return deepcopy(asdict(self))


@dataclass(slots=True)
class InteractionRequest:
    """用户追问、候选选择和有副作用动作确认。"""

    kind: str
    question: str
    options: list[Any] = field(default_factory=list)
    pending_decision: dict[str, Any] | None = None
    decision_hash: str | None = None
    interaction_id: str = field(default_factory=lambda: new_id("interaction"))
    created_at: str = field(default_factory=now_iso)

    def __post_init__(self) -> None:
        if self.kind not in INTERACTION_KINDS:
            raise ValueError(f"不支持的 InteractionRequest.kind：{self.kind}")

    def to_dict(self) -> dict[str, Any]:
        return deepcopy(asdict(self))


@dataclass(slots=True)
class TaskState:
    """跨策划轮次持续存在的紧凑任务状态。"""

    task_id: str
    original_input: str
    goal: dict[str, Any]
    status: str = "running"
    version: int = 1
    user_events: list[dict[str, Any]] = field(default_factory=list)
    known_slots: dict[str, Any] = field(default_factory=dict)
    missing_slots: list[str] = field(default_factory=list)
    facts: dict[str, Any] = field(default_factory=dict)
    last_decision: dict[str, Any] | None = None
    last_observation: dict[str, Any] | None = None
    pending_interaction: dict[str, Any] | None = None
    pending_decision: dict[str, Any] | None = None
    approved_action_hashes: list[str] = field(default_factory=list)
    executed_action_hashes: list[str] = field(default_factory=list)
    completed_actions: list[dict[str, Any]] = field(default_factory=list)
    decision_signatures: list[str] = field(default_factory=list)
    retry_counts: dict[str, int] = field(default_factory=dict)
    step_count: int = 0
    max_steps: int = 20
    final_answer: str | None = None
    error_text: str | None = None
    created_at: str = field(default_factory=now_iso)
    updated_at: str = field(default_factory=now_iso)

    def __post_init__(self) -> None:
        if self.status not in TASK_STATUSES:
            raise ValueError(f"不支持的 TaskState.status：{self.status}")

    def to_dict(self) -> dict[str, Any]:
        return deepcopy(asdict(self))

    def planner_view(self) -> dict[str, Any]:
        """只把策划所需的公开状态交给 LLM，不包含私有配置。"""

        return {
            "task_id": self.task_id,
            "status": self.status,
            "goal": deepcopy(self.goal),
            "original_input": self.original_input,
            "user_events": deepcopy(self.user_events[-10:]),
            "known_slots": deepcopy(self.known_slots),
            "missing_slots": deepcopy(self.missing_slots),
            "facts": deepcopy(self.facts),
            "last_decision": deepcopy(self.last_decision),
            "last_observation": deepcopy(self.last_observation),
            "step_count": self.step_count,
            "max_steps": self.max_steps,
        }


def initial_task_state(original_input: str, goal: dict[str, Any] | None = None, max_steps: int = 20) -> TaskState:
    text = original_input.strip()
    if not text:
        raise ValueError("任务输入不能为空。")
    return TaskState(
        task_id=new_id("task"),
        original_input=text,
        goal=deepcopy(goal) if isinstance(goal, dict) and goal else {
            "summary": text,
            "success_criteria": ["用户目标已完成，或已经给出明确可执行的下一步说明。"],
        },
        user_events=[{"event_type": "user_input", "content": text, "created_at": now_iso()}],
        max_steps=max(1, max_steps),
    )
