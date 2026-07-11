"""third_two 调试页面与只读观测 API。"""

from __future__ import annotations

import os
from typing import Any

from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import HTMLResponse

from third.agents.shared.config import load_config

from ..contracts import TaskState
from ..repository import InMemoryTaskRepository
from .page import debug_page_html


def create_debug_router(repository: InMemoryTaskRepository) -> APIRouter:
    router = APIRouter(prefix="/debug", tags=["third_two debug"])

    @router.get("", response_class=HTMLResponse, include_in_schema=False)
    def debug_page() -> HTMLResponse:
        _ensure_debug_enabled()
        return HTMLResponse(debug_page_html())

    @router.get("/health")
    def debug_health() -> dict[str, Any]:
        config = load_config()
        if not config.debug_enabled:
            return {"debugEnabled": False, "modes": {}, "checks": []}
        planner_mode = os.getenv("THIRD_TWO_PLANNER_MODE", "llm").strip().lower() or "llm"
        planner_model = os.getenv("THIRD_TWO_PLANNER_MODEL", "").strip() or config.workflowagent_model
        return {
            "debugEnabled": True,
            "modes": {
                "runtime": "rolling-planner",
                "planner": planner_mode,
                "model": planner_model,
                "llmRoute": config.llm_route_mode,
                "feishu": "real" if config.feishu_use_real else "mock",
                "repository": "memory",
            },
            "checks": [
                _check("llmProvider", config.has_usable_llm_provider, "已复用 third LLM 出口"),
                _check(
                    "feishu",
                    not config.feishu_use_real or config.can_read_real_feishu,
                    "真实飞书配置可用" if config.feishu_use_real else "当前使用 third mock 飞书配置",
                ),
                _check("debug", True, "沿用 THIRD_DEBUG_ENABLED"),
            ],
            "note": "仅展示脱敏后的运行模式；模型、飞书和出口配置均沿用 third。",
        }

    @router.get("/tasks")
    def list_debug_tasks(limit: int = Query(default=50, ge=1, le=200)) -> dict[str, Any]:
        _ensure_debug_enabled()
        return {"tasks": [_task_summary(state) for state in repository.list_tasks(limit)]}

    @router.get("/tasks/latest")
    def latest_debug_task() -> dict[str, Any]:
        _ensure_debug_enabled()
        tasks = repository.list_tasks(1)
        return {"task": _task_summary(tasks[0]) if tasks else None}

    @router.get("/tasks/{task_id}/timeline")
    def task_timeline(task_id: str) -> dict[str, Any]:
        _ensure_debug_enabled()
        state = repository.get_task(task_id)
        if not state:
            raise HTTPException(status_code=404, detail=f"third_two task 不存在：{task_id}")
        steps = list(state.completed_actions)
        if state.pending_decision:
            pending = state.pending_decision
            steps.append(
                {
                    "action_id": pending.get("action_id"),
                    "action_name": pending.get("action_name"),
                    "status": "waiting_confirmation",
                    "decision_summary": pending.get("decision_summary"),
                    "expected_outcome": pending.get("expected_outcome"),
                    "observation_summary": "动作尚未执行，正在等待用户确认。",
                    "artifact_ref": None,
                    "error_code": None,
                    "created_at": state.updated_at,
                }
            )
        return {
            "task": _task_summary(state),
            "steps": [{"step": index, **item} for index, item in enumerate(steps, start=1)],
            "userEvents": state.user_events,
            "lastDecision": state.last_decision,
            "lastObservation": state.last_observation,
            "artifacts": repository.list_artifacts(task_id),
        }

    return router


def _ensure_debug_enabled() -> None:
    if not load_config().debug_enabled:
        raise HTTPException(status_code=404, detail="third_two debug 未启用。")


def _task_summary(state: TaskState) -> dict[str, Any]:
    return {
        "taskId": state.task_id,
        "title": state.goal.get("summary") or state.original_input,
        "originalInput": state.original_input,
        "status": state.status,
        "stepCount": state.step_count,
        "maxSteps": state.max_steps,
        "interactionKind": (state.pending_interaction or {}).get("kind"),
        "createdAt": state.created_at,
        "updatedAt": state.updated_at,
    }


def _check(name: str, ok: bool, detail: str) -> dict[str, str]:
    return {"name": name, "status": "ok" if ok else "error", "detail": detail}
