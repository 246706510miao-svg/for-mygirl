from __future__ import annotations

import unittest
from types import SimpleNamespace
from unittest.mock import patch

from third_two.actions import ActionDispatcher, _observation_from_tool
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

    def test_table_header_delete_keeps_all_actions_for_the_final_confirmation(self) -> None:
        repository = InMemoryTaskRepository()
        state = repository.create_task("把附件、单选这两个表头删除掉，把文本表头换成内容")
        repository.save_artifact(
            state.task_id,
            "table_schema",
            {
                "table_fields": {
                    "source": "mock",
                    "field_names": ["附件", "单选", "文本"],
                    "fields": [
                        {"field_id": "field_attachment", "field_name": "附件", "type": 17, "property": {}},
                        {"field_id": "field_single", "field_name": "单选", "type": 3, "property": {}},
                        {"field_id": "field_text", "field_name": "文本", "type": 1, "property": {}},
                    ],
                }
            },
        )
        decision = ActionDecision(
            action_name="prepare_schema_change",
            arguments={
                "actions": [
                    {"action": "delete_field", "field_name": "附件"},
                    {"action": "delete_field", "field_name": "单选"},
                    {"action": "update_field", "source_field_name": "文本", "new_field_name": "内容"},
                ]
            },
        )
        config = SimpleNamespace(
            feishu_use_real=False,
            can_write_real_feishu=True,
            missing_real_feishu_fields=[],
            table_context={
                "app_token": "app_mock",
                "table_id": "table_mock",
                "table_name": "test",
                "view_id": "",
                "user_id_type": "open_id",
            },
        )

        with patch("third_two.actions.load_config", return_value=config):
            observation = ActionDispatcher().dispatch(decision, state, repository)

        self.assertEqual(observation.status, "success")
        self.assertEqual([item["action"] for item in observation.data["request"]["actions"]], ["delete_field", "delete_field", "update_field"])
        self.assertEqual(observation.data["preview"]["delete_field_names"], ["附件", "单选"])
        self.assertIn("不会自动回滚", observation.data["preview"]["warning"])

    def test_permission_failure_is_terminal_and_partial_failure_is_not_retried(self) -> None:
        decision = ActionDecision(action_name="change_fields")
        permission = _observation_from_tool(
            decision,
            {"error": "飞书 HTTP 403：permission denied", "summary": "字段变更失败"},
            "schema_change_result",
        )
        partial = _observation_from_tool(
            decision,
            {
                "error": "connection reset",
                "summary": "字段变更部分完成",
                "partial_success": True,
                "executed_action_count": 1,
                "planned_action_count": 3,
                "remaining_action_count": 1,
            },
            "schema_change_result",
        )

        self.assertEqual(permission.status, "terminal_error")
        self.assertEqual(permission.error_code, "tool_permission_denied")
        self.assertIn("协作者权限", permission.summary)
        self.assertEqual(partial.status, "terminal_error")
        self.assertEqual(partial.error_code, "tool_partial_failure")
        self.assertFalse(partial.recoverable)


if __name__ == "__main__":
    unittest.main()
