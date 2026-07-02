from __future__ import annotations

import unittest
from types import SimpleNamespace
from unittest.mock import patch

from third import worker


class FakeRepository:
    def __init__(self) -> None:
        self.sessions: list[tuple[str, str, str]] = []

    def update_session(self, session_id: str, **fields: str) -> None:
        self.sessions.append((session_id, str(fields.get("status")), str(fields.get("error_text"))))


class FakeRuntimeStore:
    def __init__(self, message: dict[str, object] | None, *, locked: bool = False, max_deliveries: int = 5) -> None:
        self.message = message
        self.locked = locked
        self.config = SimpleNamespace(workflow_max_deliveries=max_deliveries)
        self.acked: list[str] = []
        self.dead_letters: list[tuple[dict[str, object], str]] = []
        self.lock_attempts: list[str] = []
        self.released: list[str] = []

    def consume_one(self, block_ms: int = 1000) -> dict[str, object] | None:
        return self.message

    def ack(self, message_id: str) -> None:
        self.acked.append(message_id)

    def dead_letter(self, message: dict[str, object], reason: str) -> str:
        self.dead_letters.append((message, reason))
        return "dead-1"

    def acquire_lock(self, session_id: str) -> bool:
        self.lock_attempts.append(session_id)
        return not self.locked

    def release_lock(self, session_id: str) -> None:
        self.released.append(session_id)


class WorkerReliabilityTests(unittest.TestCase):
    def test_process_one_dead_letters_message_after_max_deliveries(self) -> None:
        repository = FakeRepository()
        runtime = FakeRuntimeStore(
            {"message_id": "1700000000000-0", "session_id": "sess_1", "delivery_count": 6},
            max_deliveries=5,
        )

        with patch.object(worker, "get_workflow_repository", return_value=repository), patch.object(worker, "get_workflow_runtime_store", return_value=runtime):
            processed = worker.process_one()

        self.assertTrue(processed)
        self.assertEqual(runtime.acked, ["1700000000000-0"])
        self.assertEqual(len(runtime.dead_letters), 1)
        self.assertEqual(repository.sessions[0][0], "sess_1")
        self.assertEqual(repository.sessions[0][1], "failed")

    def test_process_one_keeps_locked_message_pending(self) -> None:
        runtime = FakeRuntimeStore(
            {"message_id": "1700000000000-1", "session_id": "sess_2", "delivery_count": 1},
            locked=True,
        )

        with patch.object(worker, "get_workflow_repository", return_value=FakeRepository()), patch.object(worker, "get_workflow_runtime_store", return_value=runtime):
            processed = worker.process_one()

        self.assertFalse(processed)
        self.assertEqual(runtime.lock_attempts, ["sess_2"])
        self.assertEqual(runtime.acked, [])
        self.assertEqual(runtime.dead_letters, [])


if __name__ == "__main__":
    unittest.main()
