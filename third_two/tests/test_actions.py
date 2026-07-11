from __future__ import annotations

import unittest

from third_two.actions import ActionDispatcher
from third_two.contracts import ActionDecision
from third_two.repository import InMemoryTaskRepository


class ActionDispatcherTests(unittest.TestCase):
    def test_empty_schema_change_actions_return_needs_input(self) -> None:
        repository = InMemoryTaskRepository()
        state = repository.create_task("我可以修改这个表头吗？")
        dispatcher = ActionDispatcher()

        observation = dispatcher.dispatch(
            ActionDecision(action_name="prepare_schema_change", arguments={"actions": []}),
            state,
            repository,
        )

        self.assertEqual(observation.status, "needs_input")
        self.assertEqual(observation.error_code, "schema_actions_missing")
        self.assertEqual(observation.artifact_key, "prepared_operation")

    def test_multiple_candidates_require_user_choice(self) -> None:
        repository = InMemoryTaskRepository()
        state = repository.create_task("更新其中一条记录")
        repository.save_artifact(
            state.task_id,
            "candidate_records",
            {
                "records": [
                    {"record_id": "rec_1", "fields": {"标题": "第一条"}},
                    {"record_id": "rec_2", "fields": {"标题": "第二条"}},
                ]
            },
        )
        dispatcher = ActionDispatcher()

        observation = dispatcher.dispatch(
            ActionDecision(action_name="match_record"),
            state,
            repository,
        )

        self.assertEqual(observation.status, "needs_input")
        self.assertEqual(observation.error_code, "candidate_choice_required")
        self.assertEqual(len(observation.data["candidates"]), 2)


if __name__ == "__main__":
    unittest.main()
