from __future__ import annotations

import unittest

from third.api import build_workflow_snapshot, build_workflow_snapshot_v1
from third.storage.repository import InMemoryWorkflowRepository
from third.workflow.registry import build_plan_from_template


class WorkflowSnapshotTests(unittest.TestCase):
    def test_snapshot_includes_waiting_confirmation_and_write_payload(self) -> None:
        repository = InMemoryWorkflowRepository()
        session = repository.create_session("今天学习了韩语，写到飞书里面去", status="waiting_user")
        plan = repository.save_plan(session["session_id"], build_plan_from_template("create_record", session["original_input"]))
        confirm_step = next(step for step in repository.list_steps(plan["plan_id"]) if step["kind"] == "confirm")
        write_payload = {
            "operation": "create_record",
            "tool_name": "tool_CreateFeishuBitableRecord",
            "tool_input_payload": {"create_request": {"records": [{"fields": {"事项名称": "韩语学习"}}]}},
            "preview": {"records": [{"fields": {"事项名称": "韩语学习"}}]},
        }
        repository.save_artifact(session["session_id"], "validation.write_payload", confirm_step["step_id"], data_json=write_payload)
        repository.create_confirmation(session["session_id"], confirm_step["step_id"], "确认执行以下飞书写入操作吗？", write_payload["preview"])

        snapshot = build_workflow_snapshot(repository, session["session_id"])

        self.assertEqual(snapshot["session"]["status"], "waiting_user")
        self.assertEqual(snapshot["decision"]["templateKey"], "create_record")
        self.assertEqual(snapshot["decision"]["intent"], "create_feishu_record")
        self.assertEqual(snapshot["confirmation"]["requestText"], "确认执行以下飞书写入操作吗？")
        self.assertEqual(snapshot["outputs"]["writePayload"]["operation"], "create_record")
        self.assertIn("validation.write_payload", snapshot["artifactsByKey"])

        snapshot_v1 = build_workflow_snapshot_v1(repository, session["session_id"])
        self.assertEqual(snapshot_v1.confirmation.confirmation_id, snapshot["confirmation"]["confirmationId"])
        self.assertEqual(snapshot_v1.confirmation.interaction_kind.value, "confirm")
        self.assertEqual(snapshot_v1.outputs.write_payload["operation"], "create_record")

    def test_snapshot_includes_draft_output(self) -> None:
        repository = InMemoryWorkflowRepository()
        session = repository.create_session("今天完成了晨间拉伸", status="success")
        repository.save_plan(session["session_id"], build_plan_from_template("record_draft", session["original_input"]))
        draft = {
            "title": "今日自律记录",
            "recordDate": "2026-06-22",
            "summary": "今天完成了晨间拉伸",
            "score": 80,
            "tags": ["运动"],
            "suggestion": "保持节奏。",
            "previewText": "今天完成了晨间拉伸",
        }
        repository.save_artifact(session["session_id"], "record.draft", None, data_json=draft)

        snapshot = build_workflow_snapshot(repository, session["session_id"])

        self.assertEqual(snapshot["decision"]["templateKey"], "record_draft")
        self.assertEqual(snapshot["outputs"]["draft"]["summary"], "今天完成了晨间拉伸")
        self.assertEqual(snapshot["outputs"]["writePayload"], None)

    def test_snapshot_includes_write_result_and_final_answer(self) -> None:
        repository = InMemoryWorkflowRepository()
        session = repository.create_session("新增一条记录", status="success")
        repository.update_session(session["session_id"], final_answer="写入成功。")
        repository.save_plan(session["session_id"], build_plan_from_template("create_record", session["original_input"]))
        repository.save_artifact(session["session_id"], "write_result", None, data_json={"summary": "写入成功。", "record_id": "rec_xxx"})
        repository.save_artifact(session["session_id"], "final.answer", None, data_json={"answer": "写入成功。"})

        snapshot = build_workflow_snapshot(repository, session["session_id"])

        self.assertEqual(snapshot["outputs"]["writeResult"]["record_id"], "rec_xxx")
        self.assertEqual(snapshot["outputs"]["finalAnswer"]["answer"], "写入成功。")

    def test_snapshot_does_not_expose_private_metadata(self) -> None:
        repository = InMemoryWorkflowRepository()
        private_metadata = {
            "feishu": {
                "account": {"app_secret": "secret-value", "tenant_access_token": "tenant-token"},
                "table": {"app_token": "app-token", "table_id": "tbl_xxx"},
            }
        }
        session = repository.create_session(
            "新增一条记录",
            status="queued",
            metadata_json={"feishu": {"configId": "feishu_tbl_1"}},
            private_metadata_json=private_metadata,
        )

        snapshot = build_workflow_snapshot(repository, session["session_id"])
        snapshot_text = str(snapshot)

        self.assertEqual(repository.get_private_metadata(session["session_id"]), private_metadata)
        self.assertNotIn("private_metadata_json", snapshot_text)
        self.assertNotIn("secret-value", snapshot_text)
        self.assertNotIn("tenant-token", snapshot_text)
        self.assertNotIn("app-token", snapshot_text)


if __name__ == "__main__":
    unittest.main()
