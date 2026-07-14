"""third_two 独立 FastAPI 对照入口。"""

from __future__ import annotations

import os
from typing import Any

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field

from .executor import RollingTaskExecutor
from .compat.router import create_compat_router
from .debug.router import create_debug_router
from .news_focus_router import create_news_focus_router
from .repository import InMemoryTaskRepository


class ContentPart(BaseModel):
    text: str = ""


class InvokeTaskRequest(BaseModel):
    content: list[ContentPart] = Field(default_factory=list)
    goal: dict[str, Any] = Field(default_factory=dict)
    private_metadata: dict[str, Any] = Field(default_factory=dict, alias="privateMetadata")
    max_steps: int | None = Field(default=None, alias="maxSteps")


class ResumeTaskRequest(BaseModel):
    interaction_id: str = Field(alias="interactionId")
    response: str
    content: list[ContentPart] = Field(default_factory=list)


def create_app(
    executor: RollingTaskExecutor | None = None,
    repository: InMemoryTaskRepository | None = None,
) -> FastAPI:
    task_repository = repository or (executor.repository if executor else InMemoryTaskRepository())
    task_executor = executor or RollingTaskExecutor(
        repository=task_repository,
        repeat_limit=_env_int("THIRD_TWO_REPEAT_LIMIT", 3),
    )
    app = FastAPI(title="for-mygirl third_two", version="0.1.0")
    app.state.task_repository = task_repository
    app.state.task_executor = task_executor
    app.include_router(create_compat_router(task_repository, task_executor))
    app.include_router(create_debug_router(task_repository))
    app.include_router(create_news_focus_router())

    @app.get("/health")
    def health() -> dict[str, str]:
        return {"status": "ok", "runtime": "rolling-planner"}

    @app.post("/tasks/invoke")
    def invoke_task(request: InvokeTaskRequest) -> dict[str, Any]:
        text = _content_text(request.content)
        if not text:
            raise HTTPException(status_code=400, detail="content[0].text 不能为空。")
        state = task_executor.create_task(
            text,
            goal=request.goal or None,
            private_metadata=request.private_metadata,
            max_steps=request.max_steps or _env_int("THIRD_TWO_MAX_STEPS", 20),
        )
        state = task_executor.run_until_boundary(state.task_id)
        return _task_response(state)

    @app.get("/tasks/{task_id}")
    def get_task(task_id: str) -> dict[str, Any]:
        state = task_repository.get_task(task_id)
        if not state:
            raise HTTPException(status_code=404, detail=f"third_two task 不存在：{task_id}")
        return _task_response(state)

    @app.post("/tasks/{task_id}/resume")
    def resume_task(task_id: str, request: ResumeTaskRequest) -> dict[str, Any]:
        try:
            state = task_executor.resume(
                task_id,
                request.interaction_id,
                request.response,
                _content_text(request.content),
            )
        except KeyError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        return _task_response(state)

    @app.get("/tasks/{task_id}/artifacts")
    def list_artifacts(task_id: str) -> dict[str, Any]:
        if not task_repository.get_task(task_id):
            raise HTTPException(status_code=404, detail=f"third_two task 不存在：{task_id}")
        return {"taskId": task_id, "artifacts": task_repository.list_artifacts(task_id)}

    return app


def _task_response(state: Any) -> dict[str, Any]:
    return {
        "taskId": state.task_id,
        "status": state.status,
        "interaction": state.pending_interaction,
        "content": [{"text": state.final_answer or ""}],
        "errorText": state.error_text,
        "taskState": state.to_dict(),
    }


def _content_text(content: list[ContentPart]) -> str:
    return content[0].text.strip() if content else ""


def _env_int(name: str, default: int) -> int:
    try:
        return max(1, int(os.getenv(name, str(default))))
    except ValueError:
        return default


app = create_app()
