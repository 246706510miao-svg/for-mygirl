"""Redis Stream 运行态封装。"""

from __future__ import annotations

import json
from collections import deque
from datetime import datetime, timezone
from typing import Any

try:
    from ..agents.shared.config import ThirdServiceConfig, load_config
    from ..agents.shared.json_utils import dumps_json
except ImportError:
    from agents.shared.config import ThirdServiceConfig, load_config
    from agents.shared.json_utils import dumps_json


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

    # 这个方法把超过重试上限的消息移入死信队列。
    def dead_letter(self, message: dict[str, Any], reason: str) -> str | None:
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
        claimed = self._claim_stale_pending()
        if claimed:
            return claimed
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
        return self._message(str(message_id), payload, "new")

    # 这个方法确认任务已消费。
    def ack(self, message_id: str) -> None:
        self.client.xack(self.config.workflow_queue_name, self.config.workflow_consumer_group, message_id)

    # 这个方法把不可恢复的消息写到死信 stream，随后由 worker ack 原消息。
    def dead_letter(self, message: dict[str, Any], reason: str) -> str | None:
        payload = {
            "session_id": str(message.get("session_id") or ""),
            "original_message_id": str(message.get("message_id") or ""),
            "reason": reason,
            "delivery_count": str(message.get("delivery_count") or 0),
            "failed_at": datetime.now(timezone.utc).isoformat(),
        }
        return str(self.client.xadd(self.config.workflow_dead_letter_queue_name, payload))

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
        self.client.set(key, dumps_json(payload), ex=self.config.workflow_artifact_ttl_seconds)

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
        self.client.set(key, dumps_json(payload), ex=self.config.workflow_idempotency_ttl_seconds)

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

    # 这个方法回收长时间没有 ack 的 pending 消息。
    def _claim_stale_pending(self) -> dict[str, Any] | None:
        try:
            response = self.client.xautoclaim(
                self.config.workflow_queue_name,
                self.config.workflow_consumer_group,
                self.config.workflow_consumer_name,
                self.config.workflow_pending_idle_ms,
                start_id="0-0",
                count=1,
            )
        except AttributeError:
            response = self.client.execute_command(
                "XAUTOCLAIM",
                self.config.workflow_queue_name,
                self.config.workflow_consumer_group,
                self.config.workflow_consumer_name,
                self.config.workflow_pending_idle_ms,
                "0-0",
                "COUNT",
                1,
            )
        if not response or len(response) < 2 or not response[1]:
            return None
        message_id, payload = response[1][0]
        return self._message(str(message_id), payload, "claimed")

    # 这个方法组装 worker 消费到的消息并附带投递次数。
    def _message(self, message_id: str, payload: dict[str, Any], source: str) -> dict[str, Any]:
        return {
            "message_id": message_id,
            "session_id": payload.get("session_id", ""),
            "delivery_count": self._delivery_count(message_id),
            "source": source,
        }

    # 这个方法读取 Redis consumer group 里的 delivery count。
    def _delivery_count(self, message_id: str) -> int:
        try:
            entries = self.client.xpending_range(
                self.config.workflow_queue_name,
                self.config.workflow_consumer_group,
                message_id,
                message_id,
                1,
            )
        except Exception:
            return 1
        if not entries:
            return 1
        entry = entries[0]
        if isinstance(entry, dict):
            return int(entry.get("times_delivered") or entry.get("delivery_count") or 1)
        if isinstance(entry, (list, tuple)) and len(entry) >= 4:
            return int(entry[3] or 1)
        return 1

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
        self.dead_letters: list[dict[str, Any]] = []
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
        message = self.queue.popleft()
        return {**message, "delivery_count": 1, "source": "new"}

    # 这个方法确认任务已消费，内存队列弹出后不需要额外处理。
    def ack(self, message_id: str) -> None:
        return None

    # 这个方法记录内存死信，便于测试。
    def dead_letter(self, message: dict[str, Any], reason: str) -> str | None:
        self.dead_letters.append({**message, "reason": reason})
        return f"dead-{len(self.dead_letters)}"

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
