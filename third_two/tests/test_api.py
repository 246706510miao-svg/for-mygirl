from __future__ import annotations

import unittest

from fastapi.testclient import TestClient

from third_two.api import create_app
from third_two.contracts import ActionDecision
from third_two.executor import RollingTaskExecutor
from third_two.planner import ScriptedPlanner
from third_two.repository import InMemoryTaskRepository


class ApiTests(unittest.TestCase):
    def test_debug_page_and_safe_health(self) -> None:
        repository = InMemoryTaskRepository()
        executor = RollingTaskExecutor(repository=repository, planner=ScriptedPlanner([]))
        client = TestClient(create_app(executor=executor, repository=repository))

        page = client.get("/debug")
        self.assertEqual(page.status_code, 200)
        self.assertIn("third_two 对话调试台", page.text)
        self.assertIn("步骤时间线", page.text)
        self.assertIn("/tasks/invoke", page.text)
        self.assertIn('textarea class="interaction-input"', page.text)
        self.assertIn("Ctrl / Cmd + Enter", page.text)
        self.assertIn("请先完成上方的小确认", page.text)
        self.assertNotIn('class="inline-input"', page.text)

        health = client.get("/debug/health")
        self.assertEqual(health.status_code, 200)
        body = health.json()
        self.assertIn("modes", body)
        serialized = health.text.lower()
        self.assertNotIn("api_key", serialized)
        self.assertNotIn("app_secret", serialized)
        self.assertNotIn("tenant_access_token", serialized)

    def test_debug_task_list_and_timeline_show_executed_steps(self) -> None:
        repository = InMemoryTaskRepository()
        planner = ScriptedPlanner(
            [
                ActionDecision(
                    action_name="ask_user",
                    arguments={"question": "请补充记录标题。"},
                    decision_summary="缺少标题，先向用户追问。",
                    expected_outcome="获得标题",
                ),
                ActionDecision(action_name="finish", arguments={"content": "信息已补齐。"}),
            ]
        )
        executor = RollingTaskExecutor(repository=repository, planner=planner)
        client = TestClient(create_app(executor=executor, repository=repository))

        invoked = client.post("/tasks/invoke", json={"content": [{"text": "新增一条记录"}]})
        task_id = invoked.json()["taskId"]

        tasks = client.get("/debug/tasks").json()["tasks"]
        self.assertEqual(tasks[0]["taskId"], task_id)
        self.assertEqual(tasks[0]["stepCount"], 1)

        timeline = client.get(f"/debug/tasks/{task_id}/timeline").json()
        self.assertEqual(len(timeline["steps"]), 1)
        self.assertEqual(timeline["steps"][0]["action_name"], "ask_user")
        self.assertEqual(timeline["steps"][0]["decision_summary"], "缺少标题，先向用户追问。")
        self.assertEqual(timeline["steps"][0]["observation_summary"], "请补充记录标题。")

    def test_invoke_and_resume_clarification(self) -> None:
        repository = InMemoryTaskRepository()
        planner = ScriptedPlanner(
            [
                ActionDecision(action_name="ask_user", arguments={"question": "要把哪个字段改成什么？"}),
                ActionDecision(action_name="finish", arguments={"content": "已记录你的字段修改目标。"}),
            ]
        )
        executor = RollingTaskExecutor(repository=repository, planner=planner)
        client = TestClient(create_app(executor=executor, repository=repository))

        invoked = client.post(
            "/tasks/invoke",
            json={
                "content": [{"text": "我想改表头"}],
                "privateMetadata": {"feishu": {"account": {"appSecret": "secret"}}},
            },
        )
        self.assertEqual(invoked.status_code, 200)
        body = invoked.json()
        self.assertEqual(body["status"], "waiting_user")
        self.assertNotIn("private_metadata", body["taskState"])

        resumed = client.post(
            f"/tasks/{body['taskId']}/resume",
            json={
                "interactionId": body["interaction"]["interaction_id"],
                "response": "answer",
                "content": [{"text": "把文本改成总结"}],
            },
        )
        self.assertEqual(resumed.status_code, 200)
        self.assertEqual(resumed.json()["status"], "completed")
        self.assertEqual(resumed.json()["content"][0]["text"], "已记录你的字段修改目标。")


if __name__ == "__main__":
    unittest.main()
