"""Redis Stream 运行态封装。"""

from __future__ import annotations

import json
from collections import deque
from typing import Any

try:
    from ..agents.shared.config import ThirdServiceConfig, load_config
except ImportError:
    from agents.shared.config import ThirdServiceConfig, load_config


# 这个基类定义 executor 和 worker 需要的运行态能力。
class WorkflowRuntimeStore:
    # 这个方法投递 workflow session 任务。
    def enqueue_session(self, session_id: str) -> str:
        raise NotImplementedError

    # 这个方法消费一条 workflow session 任务。
    def consume_one(self, block_ms: int = 1000) -> dict[str, Any] | None:
        raise NotImplementedError

    # 这个方法确认任务已消费。
    def ack(self, message_id: str) -> None:
        raise NotImplementedError

    # 这个方法获取 session 执行锁。
    def acquire_lock(self, session_id: str) -> bool:
        raise NotImplementedError

    # 这个方法释放 session 执行锁。
    def release_lock(self, session_id: str) -> None:
        raise NotImplementedError

    # 这个方法缓存当前步骤游标。
    def set_cursor(self, session_id: str, step_id: str) -> None:
        raise NotImplementedError

    # 这个方法读取当前步骤游标。
    def get_cursor(self, session_id: str) -> str | None:
        raise NotImplementedError

    # 这个方法缓存短期 artifact。
    def set_temp_artifact(self, session_id: str, artifact_key: str, payload: dict[str, Any]) -> None:
        raise NotImplementedError

    # 这个方法读取短期 artifact。
    def get_temp_artifact(self, session_id: str, artifact_key: str) -> dict[str, Any] | None:
        raise NotImplementedError

    # 这个方法写入短期幂等缓存。
    def set_idempotency(self, idempotency_key: str, payload: dict[str, Any]) -> None:
        raise NotImplementedError

    # 这个方法读取短期幂等缓存。
    def get_idempotency(self, idempotency_key: str) -> dict[str, Any] | None:
        raise NotImplementedError

    # 这个方法获取飞书字段刷新锁。
    def acquire_schema_refresh_lock(self, table_key: str, ttl_seconds: int = 120) -> bool:
        raise NotImplementedError


# 这个类使用真实 Redis Stream、String 和 Hash 保存运行态。
class RedisWorkflowRuntimeStore(WorkflowRuntimeStore):
    # 这个构造函数创建 Redis 客户端并确保 consumer group 存在。
    def __init__(self, config: ThirdServiceConfig | None = None) -> None:
        self.config = config or load_config()
        try:
            import redis
        except ImportError as exc:
            raise RuntimeError("缺少 redis 依赖，无法使用 RedisWorkflowRuntimeStore。") from exc
        self.client = redis.Redis.from_url(self.config.redis_url, decode_responses=True)
        self._ensure_group()

    # 这个方法投递 workflow session 任务。
    def enqueue_session(self, session_id: str) -> str:
        return str(self.client.xadd(self.config.workflow_queue_name, {"session_id": session_id}))

    # 这个方法消费一条 workflow session 任务。
    def consume_one(self, block_ms: int = 1000) -> dict[str, Any] | None:
        response = self.client.xreadgroup(
            groupname=self.config.workflow_consumer_group,
            consumername=self.config.workflow_consumer_name,
            streams={self.config.workflow_queue_name: ">"},
            count=1,
            block=block_ms,
        )
        if not response:
            return None
        _, messages = response[0]
        message_id, payload = messages[0]
        return {"message_id": message_id, "session_id": payload.get("session_id", "")}

    # 这个方法确认任务已消费。
    def ack(self, message_id: str) -> None:
        self.client.xack(self.config.workflow_queue_name, self.config.workflow_consumer_group, message_id)

    # 这个方法获取 session 执行锁。
    def acquire_lock(self, session_id: str) -> bool:
        key = f"third:workflow:lock:{session_id}"
        return bool(self.client.set(key, "1", nx=True, ex=self.config.workflow_lock_ttl_seconds))

    # 这个方法释放 session 执行锁。
    def release_lock(self, session_id: str) -> None:
        self.client.delete(f"third:workflow:lock:{session_id}")

    # 这个方法缓存当前步骤游标。
    def set_cursor(self, session_id: str, step_id: str) -> None:
        self.client.set(f"third:workflow:cursor:{session_id}", step_id, ex=86400)

    # 这个方法读取当前步骤游标。
    def get_cursor(self, session_id: str) -> str | None:
        value = self.client.get(f"third:workflow:cursor:{session_id}")
        return str(value) if value else None

    # 这个方法缓存短期 artifact。
    def set_temp_artifact(self, session_id: str, artifact_key: str, payload: dict[str, Any]) -> None:
        key = f"third:artifact:temp:{session_id}:{artifact_key}"
        self.client.set(key, json.dumps(payload, ensure_ascii=False), ex=self.config.workflow_artifact_ttl_seconds)

    # 这个方法读取短期 artifact。
    def get_temp_artifact(self, session_id: str, artifact_key: str) -> dict[str, Any] | None:
        raw_value = self.client.get(f"third:artifact:temp:{session_id}:{artifact_key}")
        if not raw_value:
            return None
        try:
            loaded = json.loads(str(raw_value))
        except json.JSONDecodeError:
            return None
        return loaded if isinstance(loaded, dict) else None

    # 这个方法写入短期幂等缓存。
    def set_idempotency(self, idempotency_key: str, payload: dict[str, Any]) -> None:
        key = f"third:idempotency:{idempotency_key}"
        self.client.set(key, json.dumps(payload, ensure_ascii=False), ex=self.config.workflow_idempotency_ttl_seconds)

    # 这个方法读取短期幂等缓存。
    def get_idempotency(self, idempotency_key: str) -> dict[str, Any] | None:
        raw_value = self.client.get(f"third:idempotency:{idempotency_key}")
        if not raw_value:
            return None
        try:
            loaded = json.loads(str(raw_value))
        except json.JSONDecodeError:
            return None
        return loaded if isinstance(loaded, dict) else None

    # 这个方法获取飞书字段刷新锁。
    def acquire_schema_refresh_lock(self, table_key: str, ttl_seconds: int = 120) -> bool:
        return bool(self.client.set(f"third:feishu:schema:refreshing:{table_key}", "1", nx=True, ex=ttl_seconds))

    # 这个方法确保 Redis Stream consumer group 存在。
    def _ensure_group(self) -> None:
        try:
            self.client.xgroup_create(self.config.workflow_queue_name, self.config.workflow_consumer_group, id="0", mkstream=True)
        except Exception as exc:
            if "BUSYGROUP" not in str(exc):
                raise


# 这个类提供无 Redis 时的内存运行态，主要用于本地 mock 调试。
class InMemoryWorkflowRuntimeStore(WorkflowRuntimeStore):
    # 这个构造函数初始化内存队列和缓存。
    def __init__(self) -> None:
        self.queue: deque[dict[str, str]] = deque()
        self.locks: set[str] = set()
        self.cursors: dict[str, str] = {}
        self.temp_artifacts: dict[str, dict[str, Any]] = {}
        self.idempotency: dict[str, dict[str, Any]] = {}
        self.schema_locks: set[str] = set()

    # 这个方法投递 workflow session 任务。
    def enqueue_session(self, session_id: str) -> str:
        message_id = f"mem-{len(self.queue) + 1}"
        self.queue.append({"message_id": message_id, "session_id": session_id})
        return message_id

    # 这个方法消费一条 workflow session 任务。
    def consume_one(self, block_ms: int = 1000) -> dict[str, Any] | None:
        if not self.queue:
            return None
        return self.queue.popleft()

    # 这个方法确认任务已消费，内存队列弹出后不需要额外处理。
    def ack(self, message_id: str) -> None:
        return None

    # 这个方法获取 session 执行锁。
    def acquire_lock(self, session_id: str) -> bool:
        if session_id in self.locks:
            return False
        self.locks.add(session_id)
        return True

    # 这个方法释放 session 执行锁。
    def release_lock(self, session_id: str) -> None:
        self.locks.discard(session_id)

    # 这个方法缓存当前步骤游标。
    def set_cursor(self, session_id: str, step_id: str) -> None:
        self.cursors[session_id] = step_id

    # 这个方法读取当前步骤游标。
    def get_cursor(self, session_id: str) -> str | None:
        return self.cursors.get(session_id)

    # 这个方法缓存短期 artifact。
    def set_temp_artifact(self, session_id: str, artifact_key: str, payload: dict[str, Any]) -> None:
        self.temp_artifacts[f"{session_id}:{artifact_key}"] = payload

    # 这个方法读取短期 artifact。
    def get_temp_artifact(self, session_id: str, artifact_key: str) -> dict[str, Any] | None:
        return self.temp_artifacts.get(f"{session_id}:{artifact_key}")

    # 这个方法写入短期幂等缓存。
    def set_idempotency(self, idempotency_key: str, payload: dict[str, Any]) -> None:
        self.idempotency[idempotency_key] = payload

    # 这个方法读取短期幂等缓存。
    def get_idempotency(self, idempotency_key: str) -> dict[str, Any] | None:
        return self.idempotency.get(idempotency_key)

    # 这个方法获取字段刷新锁。
    def acquire_schema_refresh_lock(self, table_key: str, ttl_seconds: int = 120) -> bool:
        if table_key in self.schema_locks:
            return False
        self.schema_locks.add(table_key)
        return True
