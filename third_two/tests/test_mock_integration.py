from __future__ import annotations

import os
import unittest
from unittest.mock import patch

from third.Tool.mock_repository import reset_mock_state
from third_two.contracts import ActionDecision
from third_two.executor import RollingTaskExecutor
from third_two.planner import ScriptedPlanner
from third_two.repository import InMemoryTaskRepository


class MockIntegrationTests(unittest.TestCase):
    def setUp(self) -> None:
        reset_mock_state()

    def tearDown(self) -> None:
        reset_mock_state()

    def test_full_create_flow_uses_real_third_tool_adapter(self) -> None:
        repository = InMemoryTaskRepository()
        planner = ScriptedPlanner(
            [
                ActionDecision(action_name="read_table_schema"),
                ActionDecision(
                    action_name="prepare_create_record",
                    arguments={"fields": {"标题": "third_two 集成测试", "内容": "滚动策划写入"}},
                ),
                ActionDecision(action_name="create_record"),
                ActionDecision(action_name="finish", arguments={"content": "mock 写入完成。"}),
            ]
        )
        executor = RollingTaskExecutor(repository=repository, planner=planner)

        with patch.dict(os.environ, {"THIRD_FEISHU_USE_REAL": "0"}, clear=False):
            state = executor.create_task("新增一条 third_two 集成测试记录")
            waiting = executor.run_until_boundary(state.task_id)
            self.assertEqual(waiting.status, "waiting_user")
            self.assertEqual(waiting.pending_interaction["kind"], "confirm")

            result = executor.resume(
                state.task_id,
                waiting.pending_interaction["interaction_id"],
                "approve",
                "确认",
            )

        self.assertEqual(result.status, "completed")
        self.assertEqual(result.final_answer, "mock 写入完成。")
        artifact_keys = [item["artifact_key"] for item in repository.list_artifacts(state.task_id)]
        self.assertEqual(
            artifact_keys,
            ["table_schema", "prepared_operation", "write_result", "final_answer"],
        )
        write_result = repository.get_latest_artifact(state.task_id, "write_result")
        self.assertEqual(write_result["data"]["backend"], "mock")
        self.assertEqual(write_result["data"]["record_count"], 1)


if __name__ == "__main__":
    unittest.main()
