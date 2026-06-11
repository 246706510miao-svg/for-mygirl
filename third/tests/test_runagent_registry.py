from __future__ import annotations

import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from third.agents.workflowagent import agent as workflowagent
from third.runtime.redis_runtime import InMemoryWorkflowRuntimeStore
from third.scripts.seed_runagent_prompts import RunAgentPromptValidationError, seed_runagent_prompts, _validate_prompt
from third.storage.models import Base, PromptRegistryModel
from third.storage.repository import InMemoryWorkflowRepository
from third.workflow import executor as workflow_executor
from third.workflow.executor import WorkflowExecutor
from third.workflow.plan_validator import PlanValidationError, validate_workflow_plan


class RunAgentRegistryTests(unittest.TestCase):
    def test_seed_runagent_prompts_upserts_prompt_registry(self) -> None:
        session_factory = _sqlite_session_factory()
        prompt_dir = Path(__file__).resolve().parents[1] / "Prompt" / "runagent"

        first_rows = seed_runagent_prompts(prompt_dir, session_factory=session_factory)
        second_rows = seed_runagent_prompts(prompt_dir, session_factory=session_factory)

        self.assertEqual(first_rows[0]["prompt_key"], "parse_feishu_record.v1")
        self.assertEqual(second_rows[0]["agent_name"], "business_agent")
        with session_factory() as session:
            stored = session.get(PromptRegistryModel, "parse_feishu_record.v1")
            self.assertIn("你是 third 第三方服务模块的 business_agent", stored.prompt_text)
            self.assertEqual(stored.agent_name, "business_agent")

    def test_seed_runagent_prompts_rejects_missing_required_field(self) -> None:
        with self.assertRaises(RunAgentPromptValidationError):
            _validate_prompt({"prompt_key": "broken"}, Path("broken.yaml"))

    def test_seed_runagent_prompts_requires_mysql_dsn_without_injected_session(self) -> None:
        with patch("third.scripts.seed_runagent_prompts.load_config", return_value=SimpleNamespace(mysql_dsn="")):
            with self.assertRaisesRegex(RuntimeError, "THIRD_MYSQL_DSN"):
                seed_runagent_prompts(Path("unused"))

    def test_seed_runagent_prompts_requires_migrated_prompt_registry(self) -> None:
        session_factory = _old_prompt_registry_session_factory()
        prompt_dir = Path(__file__).resolve().parents[1] / "Prompt" / "runagent"

        with self.assertRaisesRegex(RuntimeError, "prompt_registry 表结构缺少"):
            seed_runagent_prompts(prompt_dir, session_factory=session_factory)

    def test_repository_lists_only_enabled_agent_prompts(self) -> None:
        repository = InMemoryWorkflowRepository()
        repository.prompts["enabled"] = {
            "prompt_key": "enabled",
            "agent_name": "business_agent",
            "enabled": True,
        }
        repository.prompts["disabled"] = {
            "prompt_key": "disabled",
            "agent_name": "business_agent",
            "enabled": False,
        }

        prompts = repository.list_agent_prompts()

        self.assertEqual([prompt["prompt_key"] for prompt in prompts], ["enabled"])

    def test_plan_validator_rejects_unregistered_agent_prompt(self) -> None:
        plan = _write_plan_with_agent("missing", "business_agent")

        with self.assertRaisesRegex(PlanValidationError, "未注册"):
            validate_workflow_plan(plan, agent_prompts=[{"prompt_key": "parse_feishu_record.v1", "agent_name": "business_agent"}])

    def test_plan_validator_rejects_agent_name_mismatch(self) -> None:
        plan = _write_plan_with_agent("parse_feishu_record.v1", "wrong_agent")

        with self.assertRaisesRegex(PlanValidationError, "不匹配"):
            validate_workflow_plan(plan, agent_prompts=[{"prompt_key": "parse_feishu_record.v1", "agent_name": "business_agent"}])

    def test_plan_validator_normalizes_tool_name_alias(self) -> None:
        plan = _write_plan_with_agent("parse_feishu_record.v1", "business_agent")
        plan["steps"][0]["name"] = plan["steps"][0].pop("tool_name")

        validated = validate_workflow_plan(
            plan,
            agent_prompts=[{"prompt_key": "parse_feishu_record.v1", "agent_name": "business_agent"}],
        )

        self.assertEqual(validated["steps"][0]["tool_name"], "tool_ReadFeishuBitableSchema")

    def test_plan_validator_rejects_write_to_feishu_as_read(self) -> None:
        plan = {
            "type": "workflow_plan",
            "version": "workflow.v1",
            "intent": "read_feishu_records",
            "risk_level": "read",
            "requires_confirmation": False,
            "original_input": "我今早看了英语，写到飞书里面",
            "steps": [
                {
                    "step_id": "step_read_records",
                    "kind": "tool",
                    "tool_name": "tool_ReadFeishuBitable",
                    "output": {"save_as": "feishu.records"},
                }
            ],
        }

        with self.assertRaisesRegex(PlanValidationError, "明显写入飞书"):
            validate_workflow_plan(plan)

    def test_executor_saves_invalid_plan_artifact(self) -> None:
        repository = InMemoryWorkflowRepository()
        session = repository.create_session("查询飞书记录", status="running")
        invalid_plan = {
            "type": "workflow_plan",
            "version": "workflow.v1",
            "intent": "read_feishu_records",
            "risk_level": "read",
            "requires_confirmation": False,
            "original_input": "查询飞书记录",
            "steps": [{"step_id": "step_read_records", "kind": "tool", "output": {"save_as": "feishu.records"}}],
        }

        with patch.object(workflow_executor, "build_workflow_plan", return_value=invalid_plan), patch.object(
            workflow_executor,
            "load_config",
            return_value=SimpleNamespace(workflowagent_use_llm=False, workflow_debug_log=False),
        ):
            result = WorkflowExecutor(repository=repository, runtime_store=InMemoryWorkflowRuntimeStore()).run_session(session["session_id"])

        artifact = repository.get_artifact(session["session_id"], "workflow.plan.invalid")
        self.assertEqual(result["status"], "failed")
        self.assertIsNotNone(artifact)
        self.assertIn("tool_name", artifact["data_json"]["error_text"])

    def test_workflowagent_prompt_includes_agent_catalog(self) -> None:
        prompt = workflowagent._append_agent_catalog(
            "base",
            [
                {
                    "prompt_key": "parse_feishu_record.v1",
                    "agent_name": "business_agent",
                    "role_name": "feishu_record_payload_parser",
                    "description": "生成写入 payload",
                    "db_address": "prompt_registry.prompt_key=parse_feishu_record.v1",
                    "input_schema_json": {},
                    "output_schema_json": {},
                    "metadata_json": {"side_effect_level": "write"},
                    "version": "1",
                    "enabled": True,
                }
            ],
        )

        self.assertIn("可用 Tool 能力目录", prompt)
        self.assertIn("tool_ReadFeishuBitableSchema", prompt)
        self.assertIn("读取当前飞书多维表格字段定义", prompt)
        self.assertIn("可用业务 Agent 目录", prompt)
        self.assertIn("parse_feishu_record.v1", prompt)
        self.assertIn("business_agent", prompt)
        self.assertIn("feishu_record_payload_parser", prompt)
        self.assertIn("metadata_json", prompt)
        self.assertIn("db_address", prompt)

    def test_workflowagent_llm_mode_requires_agent_catalog(self) -> None:
        config = SimpleNamespace(workflowagent_use_llm=True, openai_api_key="sk-test", workflowagent_model="gpt-test")

        with self.assertRaisesRegex(RuntimeError, "prompt_registry"):
            workflowagent.build_workflow_plan("新增记录", config=config, agent_prompts=[])

    def test_rule_intent_detects_write_to_feishu(self) -> None:
        config = SimpleNamespace(workflowagent_use_llm=False)

        plan = workflowagent.build_workflow_plan("我今早看了一个半小时英语，写到飞书里面", config=config)

        self.assertEqual(plan["intent"], "create_feishu_record")
        self.assertEqual([step["kind"] for step in plan["steps"]], ["tool", "agent", "validation", "confirm", "tool"])


def _sqlite_session_factory() -> sessionmaker:
    engine = create_engine("sqlite:///:memory:", future=True)
    Base.metadata.create_all(engine)
    return sessionmaker(bind=engine, autoflush=False, expire_on_commit=False, future=True)


def _old_prompt_registry_session_factory() -> sessionmaker:
    engine = create_engine("sqlite:///:memory:", future=True)
    with engine.begin() as connection:
        connection.exec_driver_sql(
            """
            CREATE TABLE prompt_registry (
                prompt_key VARCHAR(128) PRIMARY KEY,
                role_name VARCHAR(128) NOT NULL,
                prompt_text TEXT NOT NULL,
                output_schema_json JSON NOT NULL,
                version VARCHAR(32) NOT NULL,
                enabled BOOLEAN NOT NULL,
                updated_at DATETIME NOT NULL
            )
            """
        )
    return sessionmaker(bind=engine, autoflush=False, expire_on_commit=False, future=True)


def _write_plan_with_agent(prompt_ref: str, agent_name: str) -> dict[str, object]:
    return {
        "type": "workflow_plan",
        "version": "workflow.v1",
        "intent": "create_feishu_record",
        "risk_level": "write",
        "requires_confirmation": True,
        "steps": [
            {
                "step_id": "step_read_schema",
                "kind": "tool",
                "tool_name": "tool_ReadFeishuBitableSchema",
                "output": {"save_as": "feishu.table_schema"},
            },
            {
                "step_id": "step_parse_payload",
                "kind": "agent",
                "agent_name": agent_name,
                "prompt_ref": prompt_ref,
                "input": {"from_session": ["feishu.table_schema"]},
                "output": {"save_as": "feishu.create_payload"},
            },
            {
                "step_id": "step_validate_payload",
                "kind": "validation",
                "input": {"from_session": ["feishu.table_schema", "feishu.create_payload"]},
                "output": {"save_as": "validation.write_payload"},
            },
            {
                "step_id": "step_confirm_write",
                "kind": "confirm",
                "input": {"from_session": ["validation.write_payload"]},
                "output": {"save_as": "confirmation.write"},
            },
            {
                "step_id": "step_write_feishu",
                "kind": "tool",
                "tool_name": "tool_CreateFeishuBitableRecord",
                "input": {"from_session": ["validation.write_payload"]},
                "output": {"save_as": "write_result"},
            },
        ],
    }


if __name__ == "__main__":
    unittest.main()
