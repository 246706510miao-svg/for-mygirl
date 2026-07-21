from __future__ import annotations

import unittest
from unittest.mock import patch

from third.api import (
    get_workflow_v1,
    internal_feishu_table_resolve_v1,
    internal_workflow_snapshot_v1,
    invoke_workflow_v1,
    resume_workflow_v1,
)
from third.runtime.redis_runtime import InMemoryWorkflowRuntimeStore
from third.storage.repository import InMemoryWorkflowRepository
from third.workflow.registry import build_plan_from_template
from third.workflow.v1_contract import FeishuTableResolveV1Request, InvokeWorkflowV1Request, ResumeWorkflowV1Request


class LegacyWorkflowV1ApiTests(unittest.TestCase):
    def test_table_resolve_uses_the_camel_case_v1_contract(self) -> None:
        request = FeishuTableResolveV1Request.model_validate(
            {
                "tableUrl": "https://example.feishu.cn/base/app_xxx?table=tbl_xxx&view=vew_xxx",
                "privateMetadata": {},
            }
        )

        response = internal_feishu_table_resolve_v1(request)
        payload = response.model_dump(by_alias=True)

        self.assertEqual(payload["status"], "ok")
        self.assertEqual(payload["sourceType"], "base")
        self.assertEqual(payload["appToken"], "app_xxx")
        self.assertNotIn("app_token", payload)

    def test_invoke_wait_resume_and_success_use_the_v1_contract(self) -> None:
        repository = InMemoryWorkflowRepository()
        runtime = InMemoryWorkflowRuntimeStore()
        invoke_request = InvokeWorkflowV1Request.model_validate(
            {
                "content": [{"text": "新增一条记录"}],
                "metadata": {"businessSessionId": "business_1", "idempotencyKey": "message_1"},
                "privateMetadata": {},
            }
        )

        with patch("third.api.get_workflow_repository", return_value=repository), patch(
            "third.api.get_workflow_runtime_store",
            return_value=runtime,
        ):
            invoked = invoke_workflow_v1(invoke_request)
            self.assertEqual(invoked.status.value, "queued")

            plan = repository.save_plan(
                invoked.session_id,
                build_plan_from_template("create_record", "新增一条记录"),
            )
            confirm_step = next(step for step in repository.list_steps(plan["plan_id"]) if step["kind"] == "confirm")
            repository.update_session(invoked.session_id, status="waiting_user")
            repository.create_confirmation(
                invoked.session_id,
                confirm_step["step_id"],
                "确认写入吗？",
                {"fields": {"事项名称": "契约测试"}},
            )

            waiting = get_workflow_v1(invoked.session_id)
            snapshot = internal_workflow_snapshot_v1(invoked.session_id)
            self.assertEqual(waiting.status.value, "waiting_user")
            self.assertEqual(snapshot.confirmation.interaction_kind.value, "confirm")

            resumed = resume_workflow_v1(
                invoked.session_id,
                ResumeWorkflowV1Request.model_validate(
                    {
                        "confirmationId": snapshot.confirmation.confirmation_id,
                        "approved": True,
                        "response": "approve",
                        "content": [{"text": "确认"}],
                    }
                ),
            )
            self.assertEqual(resumed.status.value, "queued")

            repository.update_session(invoked.session_id, status="success", final_answer="写入完成")
            completed = get_workflow_v1(invoked.session_id)
            self.assertEqual(completed.status.value, "success")
            self.assertEqual(completed.content[0].text, "写入完成")


if __name__ == "__main__":
    unittest.main()
