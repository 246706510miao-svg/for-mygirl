"""third_two TaskState、Artifact 和私有上下文 Repository。"""

from __future__ import annotations

from copy import deepcopy
from threading import RLock
from typing import Any

from .contracts import TaskState, initial_task_state, new_id, now_iso


class InMemoryTaskRepository:
    """对照版默认内存实现；接口刻意保持可替换为 MySQL。"""

    def __init__(self) -> None:
        self._tasks: dict[str, TaskState] = {}
        self._artifacts: dict[str, list[dict[str, Any]]] = {}
        self._private_metadata: dict[str, dict[str, Any]] = {}
        self._lock = RLock()

    def create_task(
        self,
        original_input: str,
        goal: dict[str, Any] | None = None,
        private_metadata: dict[str, Any] | None = None,
        max_steps: int = 20,
    ) -> TaskState:
        state = initial_task_state(original_input, goal=goal, max_steps=max_steps)
        with self._lock:
            self._tasks[state.task_id] = deepcopy(state)
            self._artifacts[state.task_id] = []
            self._private_metadata[state.task_id] = deepcopy(private_metadata or {})
        return deepcopy(state)

    def get_task(self, task_id: str) -> TaskState | None:
        with self._lock:
            state = self._tasks.get(task_id)
            return deepcopy(state) if state else None

    def list_tasks(self, limit: int = 50) -> list[TaskState]:
        """按最近更新时间返回任务，供调试台展示，不暴露私有 metadata。"""

        with self._lock:
            states = sorted(self._tasks.values(), key=lambda item: item.updated_at, reverse=True)
            return deepcopy(states[: max(1, limit)])

    def save_task(self, state: TaskState) -> TaskState:
        state.updated_at = now_iso()
        state.version += 1
        with self._lock:
            if state.task_id not in self._tasks:
                raise KeyError(f"third_two task 不存在：{state.task_id}")
            self._tasks[state.task_id] = deepcopy(state)
        return deepcopy(state)

    def save_artifact(self, task_id: str, artifact_key: str, data: dict[str, Any]) -> dict[str, Any]:
        artifact = {
            "artifact_id": new_id("artifact"),
            "task_id": task_id,
            "artifact_key": artifact_key,
            "data": deepcopy(data),
            "created_at": now_iso(),
        }
        with self._lock:
            if task_id not in self._tasks:
                raise KeyError(f"third_two task 不存在：{task_id}")
            self._artifacts.setdefault(task_id, []).append(artifact)
        return deepcopy(artifact)

    def get_latest_artifact(self, task_id: str, artifact_key: str) -> dict[str, Any] | None:
        with self._lock:
            for artifact in reversed(self._artifacts.get(task_id, [])):
                if artifact["artifact_key"] == artifact_key:
                    return deepcopy(artifact)
        return None

    def list_artifacts(self, task_id: str) -> list[dict[str, Any]]:
        with self._lock:
            return deepcopy(self._artifacts.get(task_id, []))

    def planner_artifacts(self, task_id: str) -> dict[str, Any]:
        """按 key 返回最新公开 Artifact，避免把整个历史重复塞进提示词。"""

        latest: dict[str, Any] = {}
        with self._lock:
            for artifact in self._artifacts.get(task_id, []):
                latest[artifact["artifact_key"]] = deepcopy(artifact["data"])
        return latest

    def get_private_metadata(self, task_id: str) -> dict[str, Any]:
        with self._lock:
            return deepcopy(self._private_metadata.get(task_id, {}))
