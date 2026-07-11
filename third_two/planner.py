"""每一轮只选择一个原子动作的滚动策划器。"""

from __future__ import annotations

import json
import os
from collections import deque
from pathlib import Path
from typing import Any, Protocol

from third.agents.shared.config import load_config
from third.agents.shared.openai_client import create_chat_openai
from third.workflow.content import load_json_object

from .action_catalog import catalog_for_planner
from .contracts import ActionDecision, TaskState


class Planner(Protocol):
    def decide(self, state: TaskState, artifacts: dict[str, Any]) -> ActionDecision:
        ...


class PlannerError(RuntimeError):
    pass


class LLMRollingPlanner:
    """使用共享 third LLM 出口，但不使用旧 workflow template。"""

    def __init__(self, model: str | None = None, prompt_path: Path | None = None) -> None:
        self.model = model
        self.prompt_path = prompt_path or Path(__file__).resolve().parent / "Prompt" / "planner.md"

    def decide(self, state: TaskState, artifacts: dict[str, Any]) -> ActionDecision:
        config = load_config()
        if not config.has_usable_llm_provider:
            raise PlannerError("third_two 策划 LLM 没有可用 provider，请配置现有 third LLM 出口。")
        prompt_text = self.prompt_path.read_text(encoding="utf-8")
        context = {
            "task_state": _compact(state.planner_view()),
            "latest_artifacts": _compact(artifacts),
            "action_catalog": catalog_for_planner(),
            "output_schema": {
                "action_name": "必须来自 action_catalog",
                "arguments": "当前动作需要的 JSON 对象",
                "expected_outcome": "本动作期望获得的事实",
                "decision_summary": "简短决策说明，不输出思维链",
                "state_patch": {
                    "known_slots": "可选对象",
                    "missing_slots": "可选字符串数组",
                    "goal": "可选目标修正",
                },
            },
        }
        full_prompt = f"{prompt_text}\n\n当前任务上下文 JSON：\n{json.dumps(context, ensure_ascii=False, default=str)}"
        try:
            response = create_chat_openai(config, self.model or config.workflowagent_model, temperature=0).invoke(full_prompt)
        except Exception as exc:
            raise PlannerError(f"third_two 策划 LLM 调用失败：{exc}") from exc
        response_text = _response_text(getattr(response, "content", ""))
        payload = load_json_object(response_text)
        if not payload:
            raise PlannerError("third_two 策划 LLM 输出不是合法 JSON 对象。")
        try:
            return ActionDecision.from_dict(payload)
        except ValueError as exc:
            raise PlannerError(str(exc)) from exc


class ConservativePlanner:
    """无 LLM 时的安全对照入口，只追问，不假装具备完整语义规划能力。"""

    def decide(self, state: TaskState, artifacts: dict[str, Any]) -> ActionDecision:
        last = state.last_observation or {}
        if last.get("status") == "no_match":
            return ActionDecision(
                action_name="ask_user",
                arguments={"question": "没有找到匹配记录。你希望新增一条记录，还是补充更精确的定位条件？", "options": ["新增记录", "补充定位条件"]},
                expected_outcome="获得用户对新增或继续匹配的选择",
                decision_summary="空候选需要用户补充。",
            )
        return ActionDecision(
            action_name="ask_user",
            arguments={"question": "当前未启用 third_two 策划 LLM，请先配置 LLM，或补充你希望执行的具体飞书动作。"},
            expected_outcome="获得具体动作信息",
            decision_summary="保守模式不猜测用户意图。",
        )


class ScriptedPlanner:
    """测试和演示用：按顺序返回预设决策，便于验证真实回流循环。"""

    def __init__(self, decisions: list[ActionDecision | dict[str, Any]]) -> None:
        self._decisions = deque(
            item if isinstance(item, ActionDecision) else ActionDecision.from_dict(item)
            for item in decisions
        )
        self.call_count = 0
        self.seen_states: list[dict[str, Any]] = []

    def decide(self, state: TaskState, artifacts: dict[str, Any]) -> ActionDecision:
        self.call_count += 1
        self.seen_states.append(state.planner_view())
        if not self._decisions:
            raise PlannerError("ScriptedPlanner 没有剩余决策。")
        return self._decisions.popleft()


def create_default_planner() -> Planner:
    mode = os.getenv("THIRD_TWO_PLANNER_MODE", "llm").strip().lower()
    if mode in {"conservative", "safe", "rule"}:
        return ConservativePlanner()
    model = os.getenv("THIRD_TWO_PLANNER_MODEL", "").strip() or None
    return LLMRollingPlanner(model=model)


def _response_text(content: Any) -> str:
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        parts: list[str] = []
        for item in content:
            if isinstance(item, dict) and item.get("text"):
                parts.append(str(item["text"]))
            elif isinstance(item, str):
                parts.append(item)
        return "\n".join(parts)
    return str(content or "")


def _compact(value: Any, depth: int = 0) -> Any:
    """限制策划上下文大小，同时保留用户任务所需事实。"""

    if depth >= 6:
        return "<max-depth>"
    if isinstance(value, dict):
        return {str(key): _compact(item, depth + 1) for key, item in list(value.items())[:80]}
    if isinstance(value, list):
        return [_compact(item, depth + 1) for item in value[:30]]
    if isinstance(value, str) and len(value) > 3000:
        return value[:3000] + "..."
    return value
