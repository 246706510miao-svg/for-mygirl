from __future__ import annotations

import unittest

from third_two.action_catalog import ACTION_CATALOG, WRITE_ACTIONS
from third_two.contracts import ActionDecision, Observation
from third_two.executor import RollingTaskExecutor
from third_two.planner import ScriptedPlanner
from third_two.repository import InMemoryTaskRepository


class FakeDispatcher:
    def __init__(self, observations: dict[str, list[Observation] | Observation]) -> None:
        self.observations = observations
        self.calls: list[str] = []

    def dispatch(self, decision, state, repository):
        self.calls.append(decision.action_name)
        configured = self.observations[decision.action_name]
        if isinstance(configured, list):
            observation = configured.pop(0)
        else:
            observation = configured
        return Observation(
            action_id=decision.action_id,
            action_name=decision.action_name,
            status=observation.status,
            summary=observation.summary,
            data=observation.data,
            fact_patch=observation.fact_patch,
            artifact_key=observation.artifact_key,
            error_code=observation.error_code,
            recoverable=observation.recoverable,
        )


class RollingTaskExecutorTests(unittest.TestCase):
    def test_catalog_contains_confirmed_fourteen_actions(self) -> None:
        self.assertEqual(len(ACTION_CATALOG), 14)
        self.assertEqual(WRITE_ACTIONS, {"create_record", "update_record", "delete_record", "change_fields"})
        self.assertTrue(all(ACTION_CATALOG[name].requires_confirmation for name in WRITE_ACTIONS))

    def test_draft_generate_metadata_uses_required_small_steps(self) -> None:
        repository = InMemoryTaskRepository()
        planner = ScriptedPlanner([])
        executor = RollingTaskExecutor(repository=repository, planner=planner)
        state = executor.create_task(
            "今天完成了服务器更新",
            goal={
                "summary": "生成记录草稿",
                "success_criteria": ["record_draft 已生成"],
                "business_context": {"operation": "draft_generate"},
            },
        )

        result = executor.run_until_boundary(state.task_id)

        self.assertEqual(result.status, "completed")
        self.assertEqual([item["action_name"] for item in result.completed_actions], ["generate_record_draft", "finish"])
        self.assertEqual(planner.call_count, 0)
        self.assertIsNotNone(repository.get_latest_artifact(state.task_id, "record_draft"))

    def test_no_match_flows_back_to_planner_before_asking_user(self) -> None:
        repository = InMemoryTaskRepository()
        planner = ScriptedPlanner(
            [
                ActionDecision(action_name="read_records", arguments={"read_request": {"operation": "search_records"}}),
                ActionDecision(
                    action_name="ask_user",
                    arguments={"question": "没有找到记录，要新增还是补充条件？", "options": ["新增", "补充条件"]},
                ),
            ]
        )
        dispatcher = FakeDispatcher(
            {
                "read_records": Observation(
                    action_id="placeholder",
                    action_name="read_records",
                    status="no_match",
                    summary="返回 0 条记录。",
                    data={"record_count": 0, "records": []},
                    artifact_key="candidate_records",
                )
            }
        )
        executor = RollingTaskExecutor(repository=repository, planner=planner, dispatcher=dispatcher)
        state = executor.create_task("完成服务器更新，写到飞书")

        result = executor.run_until_boundary(state.task_id)

        self.assertEqual(result.status, "waiting_user")
        self.assertEqual(planner.call_count, 2)
        self.assertEqual(dispatcher.calls, ["read_records"])
        self.assertEqual([item["status"] for item in result.completed_actions], ["no_match", "needs_input"])
        self.assertEqual(result.pending_interaction["kind"], "clarify")

    def test_clarification_reply_reenters_planner_and_finishes(self) -> None:
        repository = InMemoryTaskRepository()
        planner = ScriptedPlanner(
            [
                ActionDecision(action_name="ask_user", arguments={"question": "要把哪个字段改成什么？"}),
                ActionDecision(action_name="finish", arguments={"content": "已收到字段修改说明。"}),
            ]
        )
        executor = RollingTaskExecutor(repository=repository, planner=planner, dispatcher=FakeDispatcher({}))
        state = executor.create_task("我可以修改表头吗？")
        waiting = executor.run_until_boundary(state.task_id)

        result = executor.resume(
            state.task_id,
            waiting.pending_interaction["interaction_id"],
            "answer",
            "把文本改成今日总结",
        )

        self.assertEqual(result.status, "completed")
        self.assertEqual(result.final_answer, "已收到字段修改说明。")
        self.assertEqual(result.user_events[-1]["content"], "把文本改成今日总结")
        self.assertEqual(planner.call_count, 2)

    def test_write_waits_for_confirmation_and_executes_once(self) -> None:
        repository = InMemoryTaskRepository()
        planner = ScriptedPlanner(
            [
                ActionDecision(action_name="create_record"),
                ActionDecision(action_name="finish", arguments={"content": "写入完成。"}),
            ]
        )
        dispatcher = FakeDispatcher(
            {
                "create_record": Observation(
                    action_id="placeholder",
                    action_name="create_record",
                    status="success",
                    summary="新增成功。",
                    data={"record_id": "rec_1"},
                    artifact_key="write_result",
                )
            }
        )
        executor = RollingTaskExecutor(repository=repository, planner=planner, dispatcher=dispatcher)
        state = executor.create_task("写一条记录")
        repository.save_artifact(
            state.task_id,
            "prepared_operation",
            {"operation": "create_record", "request": {"fields": {"内容": "测试"}}},
        )

        waiting = executor.run_until_boundary(state.task_id)
        self.assertEqual(waiting.status, "waiting_user")
        self.assertEqual(waiting.pending_interaction["kind"], "confirm")
        self.assertEqual(waiting.pending_interaction["preview"]["operation"], "create_record")
        self.assertTrue(waiting.pending_interaction["decision_hash"])
        self.assertEqual(dispatcher.calls, [])

        result = executor.resume(
            state.task_id,
            waiting.pending_interaction["interaction_id"],
            "approve",
            "确认",
        )
        self.assertEqual(result.status, "completed")
        self.assertEqual(dispatcher.calls, ["create_record"])
        self.assertEqual(len(result.executed_action_hashes), 1)

    def test_write_without_prepared_operation_flows_back_instead_of_confirming(self) -> None:
        repository = InMemoryTaskRepository()
        planner = ScriptedPlanner(
            [
                ActionDecision(action_name="create_record"),
                ActionDecision(action_name="ask_user", arguments={"question": "还缺少要写入的字段和值。"}),
            ]
        )
        dispatcher = FakeDispatcher({})
        executor = RollingTaskExecutor(repository=repository, planner=planner, dispatcher=dispatcher)
        state = executor.create_task("写一条记录")

        result = executor.run_until_boundary(state.task_id)

        self.assertEqual(result.status, "waiting_user")
        self.assertEqual(result.completed_actions[0]["status"], "needs_input")
        self.assertEqual(result.pending_interaction["kind"], "clarify")
        self.assertEqual(dispatcher.calls, [])

    def test_user_can_modify_pending_write_before_execution(self) -> None:
        repository = InMemoryTaskRepository()
        planner = ScriptedPlanner(
            [
                ActionDecision(action_name="create_record"),
                ActionDecision(action_name="finish", arguments={"content": "已收到修改，尚未执行写入。"}),
            ]
        )
        dispatcher = FakeDispatcher({})
        executor = RollingTaskExecutor(repository=repository, planner=planner, dispatcher=dispatcher)
        state = executor.create_task("写一条记录")
        repository.save_artifact(
            state.task_id,
            "prepared_operation",
            {"operation": "create_record", "request": {"fields": {"内容": "旧内容"}}},
        )
        waiting = executor.run_until_boundary(state.task_id)

        result = executor.resume(
            state.task_id,
            waiting.pending_interaction["interaction_id"],
            "modify",
            "把内容改成新内容",
        )

        self.assertEqual(result.status, "completed")
        self.assertEqual(result.user_events[-1]["event_type"], "user_modification")
        self.assertEqual(dispatcher.calls, [])

    def test_user_can_cancel_pending_write(self) -> None:
        repository = InMemoryTaskRepository()
        planner = ScriptedPlanner([ActionDecision(action_name="create_record")])
        dispatcher = FakeDispatcher({})
        executor = RollingTaskExecutor(repository=repository, planner=planner, dispatcher=dispatcher)
        state = executor.create_task("写一条记录")
        repository.save_artifact(
            state.task_id,
            "prepared_operation",
            {"operation": "create_record", "request": {"fields": {"内容": "测试"}}},
        )
        waiting = executor.run_until_boundary(state.task_id)

        result = executor.resume(
            state.task_id,
            waiting.pending_interaction["interaction_id"],
            "cancel",
        )

        self.assertEqual(result.status, "cancelled")
        self.assertEqual(result.final_answer, "已取消本次任务。")
        self.assertEqual(dispatcher.calls, [])

    def test_repeated_action_is_stopped(self) -> None:
        repository = InMemoryTaskRepository()
        planner = ScriptedPlanner(
            [
                ActionDecision(action_name="read_table_schema"),
                ActionDecision(action_name="read_table_schema"),
                ActionDecision(action_name="read_table_schema"),
            ]
        )
        observations = [
            Observation("placeholder", "read_table_schema", "success", data={"field_names": ["文本"]}, artifact_key="table_schema"),
            Observation("placeholder", "read_table_schema", "success", data={"field_names": ["文本"]}, artifact_key="table_schema"),
        ]
        dispatcher = FakeDispatcher({"read_table_schema": observations})
        executor = RollingTaskExecutor(repository=repository, planner=planner, dispatcher=dispatcher, repeat_limit=3)
        state = executor.create_task("读取字段")

        result = executor.run_until_boundary(state.task_id)

        self.assertEqual(result.status, "failed")
        self.assertIn("连续选择相同动作", result.error_text)
        self.assertEqual(dispatcher.calls, ["read_table_schema", "read_table_schema"])

    def test_private_metadata_is_not_part_of_task_state(self) -> None:
        repository = InMemoryTaskRepository()
        state = repository.create_task("测试", private_metadata={"feishu": {"app_secret": "secret"}})

        self.assertNotIn("private_metadata", state.to_dict())
        self.assertEqual(repository.get_private_metadata(state.task_id)["feishu"]["app_secret"], "secret")


if __name__ == "__main__":
    unittest.main()
