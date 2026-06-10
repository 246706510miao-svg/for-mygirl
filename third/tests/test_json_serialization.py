from __future__ import annotations

import json
import unittest
from datetime import date, datetime
from types import SimpleNamespace

from third.agents.shared.json_utils import dumps_json, to_jsonable
from third.runtime.redis_runtime import RedisWorkflowRuntimeStore
from third.workflow.executor import WorkflowExecutor


class FakeRedisClient:
    def __init__(self) -> None:
        self.values: dict[str, dict[str, object]] = {}

    def set(self, key: str, value: str, ex: int | None = None, **_: object) -> bool:
        self.values[key] = {"value": value, "ex": ex}
        return True

    def get(self, key: str) -> str | None:
        row = self.values.get(key)
        return str(row["value"]) if row else None


class FakeRepository:
    def __init__(self) -> None:
        self.expires_at = None

    def get_idempotency_key(self, _: str) -> None:
        return None

    def save_idempotency_key(
        self,
        idempotency_key: str,
        session_id: str,
        operation_type: str,
        target_service: str,
        payload_hash: str,
        status: str,
        result_artifact_id: str | None = None,
        expires_at: datetime | None = None,
    ) -> dict[str, object]:
        self.expires_at = expires_at
        return {
            "idempotency_key": idempotency_key,
            "session_id": session_id,
            "operation_type": operation_type,
            "target_service": target_service,
            "payload_hash": payload_hash,
            "status": status,
            "result_artifact_id": result_artifact_id,
            "expires_at": expires_at,
            "created_at": datetime(2026, 6, 10, 12, 0, 0),
        }


class FakeRuntimeStore:
    def __init__(self) -> None:
        self.payload: dict[str, object] | None = None

    def set_idempotency(self, _: str, payload: dict[str, object]) -> None:
        self.payload = payload


def redis_store_with_fake_client() -> tuple[RedisWorkflowRuntimeStore, FakeRedisClient]:
    store = object.__new__(RedisWorkflowRuntimeStore)
    store.config = SimpleNamespace(
        workflow_artifact_ttl_seconds=3600,
        workflow_idempotency_ttl_seconds=604800,
    )
    store.client = FakeRedisClient()
    return store, store.client


class JsonSerializationTests(unittest.TestCase):
    def test_to_jsonable_recursively_converts_dates(self) -> None:
        payload = {
            "created_at": datetime(2026, 6, 10, 12, 30, 45),
            "items": [{"day": date(2026, 6, 10)}],
        }

        jsonable = to_jsonable(payload)

        self.assertEqual(jsonable["created_at"], "2026-06-10T12:30:45")
        self.assertEqual(jsonable["items"][0]["day"], "2026-06-10")
        self.assertEqual(json.loads(dumps_json(payload))["created_at"], "2026-06-10T12:30:45")

    def test_temp_artifact_serializes_datetime_for_redis(self) -> None:
        store, client = redis_store_with_fake_client()
        payload = {
            "artifact_id": "art_1",
            "created_at": datetime(2026, 6, 10, 8, 0, 0),
            "expires_at": None,
            "data_json": {"expires_at": datetime(2026, 6, 17, 8, 0, 0)},
        }

        store.set_temp_artifact("sess_1", "validation.write_payload", payload)

        raw = client.values["third:artifact:temp:sess_1:validation.write_payload"]["value"]
        loaded = json.loads(str(raw))
        self.assertEqual(loaded["created_at"], "2026-06-10T08:00:00")
        self.assertEqual(loaded["data_json"]["expires_at"], "2026-06-17T08:00:00")
        self.assertEqual(store.get_temp_artifact("sess_1", "validation.write_payload"), loaded)

    def test_idempotency_serializes_datetime_for_redis(self) -> None:
        store, client = redis_store_with_fake_client()
        payload = {
            "idempotency_key": "create_record:feishu_bitable:hash",
            "status": "running",
            "created_at": datetime(2026, 6, 10, 9, 0, 0),
            "expires_at": datetime(2026, 6, 17, 9, 0, 0),
        }

        store.set_idempotency("idem_1", payload)

        raw = client.values["third:idempotency:idem_1"]["value"]
        loaded = json.loads(str(raw))
        self.assertEqual(loaded["created_at"], "2026-06-10T09:00:00")
        self.assertEqual(loaded["expires_at"], "2026-06-17T09:00:00")
        self.assertEqual(store.get_idempotency("idem_1"), loaded)

    def test_executor_parses_idempotency_expires_at_before_repository_write(self) -> None:
        repository = FakeRepository()
        runtime_store = FakeRuntimeStore()
        executor = WorkflowExecutor(repository=repository, runtime_store=runtime_store)
        artifact = {
            "data_json": {
                "idempotency_key": "create_record:feishu_bitable:hash",
                "operation": "create_record",
                "payload_hash": "hash",
                "expires_at": "2026-06-17T10:00:00",
            }
        }

        executor._save_idempotency("sess_1", artifact)

        self.assertEqual(repository.expires_at, datetime(2026, 6, 17, 10, 0, 0))
        self.assertIsInstance(runtime_store.payload, dict)


if __name__ == "__main__":
    unittest.main()
