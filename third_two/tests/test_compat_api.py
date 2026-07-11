from __future__ import annotations

import os
import unittest
from unittest.mock import patch

from fastapi.testclient import TestClient

from third.Tool.mock_repository import reset_mock_state
from third_two.api import create_app
from third_two.contracts import ActionDecision
from third_two.executor import RollingTaskExecutor
from third_two.planner import ScriptedPlanner
from third_two.repository import InMemoryTaskRepository


class CompatibilityApiTests(unittest.TestCase):
    def setUp(self) -> None:
        reset_mock_state()

    def tearDown(self) -> None:
        reset_mock_state()

    def test_draft_generate_preserves_backend_workflow_contract(self) -> None:
        repository = InMemoryTaskRepository()
        executor = RollingTaskExecutor(repository=repository, planner=ScriptedPlanner([]))
        client = TestClient(create_app(executor=executor, repository=repository))

        invoked = client.post(
            "/workflows/invoke",
            json={
                "content": [{"text": "今天完成了服务器更新"}],
                "metadata": {"operation": "draft_generate", "businessSessionId": "session_1"},
                "privateMetadata": {},
            },
        )

        self.assertEqual(invoked.status_code, 200)
        body = invoked.json()
        self.assertEqual(body["status"], "success")
        self.assertTrue(body["session_id"].startswith("task_"))

        snapshot = client.get(f"/internal/workflows/{body['session_id']}/snapshot").json()
        self.assertEqual(snapshot["session"]["metadata"]["operation"], "draft_generate")
        self.assertEqual(snapshot["outputs"]["draft"]["source"], "rule")
        self.assertEqual(snapshot["decision"]["templateKey"], "third_two.rolling")

    def test_write_confirmation_maps_to_old_confirmation_and_snapshot(self) -> None:
        repository = InMemoryTaskRepository()
        planner = ScriptedPlanner(
            [
                ActionDecision(action_name="prepare_create_record", arguments={"fields": {"标题": "兼容层测试"}}),
                ActionDecision(action_name="create_record"),
                ActionDecision(action_name="finish", arguments={"content": "写入完成。"}),
            ]
        )
        executor = RollingTaskExecutor(repository=repository, planner=planner)
        client = TestClient(create_app(executor=executor, repository=repository))

        with patch.dict(os.environ, {"THIRD_FEISHU_USE_REAL": "0"}, clear=False):
            invoked = client.post(
                "/workflows/invoke",
                json={"content": [{"text": "新增标题为兼容层测试的记录"}], "metadata": {}, "privateMetadata": {}},
            )
            body = invoked.json()
            self.assertEqual(body["status"], "waiting_user")
            self.assertEqual(body["confirmation"]["interaction_kind"], "confirm")

            snapshot = client.get(f"/internal/workflows/{body['session_id']}/snapshot").json()
            self.assertEqual(snapshot["outputs"]["writePayload"]["operation"], "create_record")
            self.assertEqual(snapshot["outputs"]["writePayload"]["preview"]["fields"]["标题"], "兼容层测试")

            resumed = client.post(
                f"/workflows/{body['session_id']}/resume",
                json={
                    "confirmation_id": body["confirmation"]["confirmation_id"],
                    "approved": True,
                    "content": [{"text": "确认"}],
                },
            )
        self.assertEqual(resumed.status_code, 200)
        self.assertEqual(resumed.json()["status"], "success")


if __name__ == "__main__":
    unittest.main()
