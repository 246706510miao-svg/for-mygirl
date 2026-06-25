from __future__ import annotations

import json
import unittest
from types import SimpleNamespace
from unittest.mock import patch

from third.Tool import mock_repository
from third.Tool import tool_ChangeFeishuBitableFields as schema_tool
from third.agents.workflowagent import agent as workflowagent
from third.workflow import agent_runner, validation
from third.workflow.plan_validator import PlanValidationError, validate_workflow_plan
from third.workflow.registry import TEMPLATE_CATALOG, TOOL_CATALOG, build_agent_catalog, build_plan_from_template
from third.workflow.tool_dispatcher import TOOL_REGISTRY


TABLE_FIELDS = {
    "source": "mock",
    "table_name": "test",
    "field_names": ["标题", "内容", "状态"],
    "fields": [
        {"field_id": "field_title", "field_name": "标题", "type": 1, "property": {}},
        {"field_id": "field_content", "field_name": "内容", "type": 1, "property": {}},
        {"field_id": "field_status", "field_name": "状态", "type": 3, "property": {"options": [{"name": "进行中"}]}},
    ],
}


class FakeConfig:
    feishu_use_real = False
    feishu_field_name_map: dict[str, str] = {}
    workflowagent_use_llm = False
    workflow_idempotency_ttl_seconds = 604800

    @property
    def table_context(self) -> dict[str, str]:
        return {
            "app_token": "app_test",
            "table_id": "tbl_test",
            "table_name": "test",
            "view_id": "vew_test",
            "user_id_type": "open_id",
        }

    @property
    def can_write_real_feishu(self) -> bool:
        return True

    @property
    def missing_real_feishu_fields(self) -> list[str]:
        return []


AGENT_PROMPTS = [
    {"prompt_key": "parse_record_draft.v1", "agent_name": "record_draft_agent"},
    {"prompt_key": "parse_feishu_record.v1", "agent_name": "business_agent"},
    {"prompt_key": "search_feishu_record.v1", "agent_name": "search_agent"},
    {"prompt_key": "parse_feishu_schema_change.v1", "agent_name": "schema_agent"},
]


class WorkflowRegistrySchemaTests(unittest.TestCase):
    def setUp(self) -> None:
        mock_repository.reset_mock_state()

    def test_tool_catalog_matches_dispatcher_registry(self) -> None:
        catalog_names = {item["tool_name"] for item in TOOL_CATALOG}

        self.assertEqual(catalog_names, set(TOOL_REGISTRY))

    def test_template_catalog_builds_valid_plans(self) -> None:
        for template in TEMPLATE_CATALOG:
            with self.subTest(template=template["template_key"]):
                plan = build_plan_from_template(str(template["template_key"]), "新增字段 情绪")
                validated = validate_workflow_plan(plan, agent_prompts=AGENT_PROMPTS)
                self.assertEqual(validated["template_key"], template["template_key"])

    def test_agent_catalog_filters_disabled_prompts(self) -> None:
        catalog = build_agent_catalog(
            [
                {"prompt_key": "enabled", "agent_name": "business_agent", "enabled": True},
                {"prompt_key": "disabled", "agent_name": "schema_agent", "enabled": False},
            ]
        )

        self.assertEqual([item["prompt_ref"] for item in catalog], ["enabled"])

    def test_rule_workflowagent_selects_schema_templates(self) -> None:
        config = SimpleNamespace(workflowagent_use_llm=False)

        schema_plan = workflowagent.build_workflow_plan("新增字段 情绪", config=config)
        report_plan = workflowagent.build_workflow_plan("我想改变表结构，让它既能记录每日内容又能记录周报和月报", config=config)
        combo_plan = workflowagent.build_workflow_plan("新增字段 情绪，然后写一条记录到飞书", config=config)

        self.assertEqual(schema_plan["template_key"], "change_schema")
        self.assertEqual(report_plan["template_key"], "change_schema")
        self.assertEqual(combo_plan["template_key"], "change_schema_then_create_record")

    def test_record_draft_agent_outputs_draft_shape(self) -> None:
        context = {
            "original_input": "生成记录草稿：今天完成了晨间拉伸，也按时吃了早餐。",
            "step": {"prompt_ref": "parse_record_draft.v1"},
            "artifacts": {},
        }

        output = agent_runner.run_business_agent(context)

        self.assertEqual(output["schema_json"]["type"], "record_draft")
        self.assertIn("previewText", output["data_json"])
        self.assertIn("draft", output["data_json"])

    def test_schema_agent_rule_outputs_report_schema_fields(self) -> None:
        context = {
            "original_input": "改变表结构，让它能记录每日内容、周报和月报",
            "step": {"prompt_ref": "parse_feishu_schema_change.v1"},
            "artifacts": {"feishu.table_schema": {"data_json": {"table_fields": TABLE_FIELDS}}},
        }

        with patch.object(agent_runner, "load_config", return_value=FakeConfig()):
            output = agent_runner.run_business_agent(context)

        actions = output["data_json"]["tool_input_payload"]["schema_change_request"]["actions"]
        self.assertIn("记录类型", [action["field_name"] for action in actions])
        record_type = next(action for action in actions if action["field_name"] == "记录类型")
        self.assertEqual(record_type["field_type"], "single_select")
        self.assertEqual(record_type["property"]["options"], ["每日内容", "周报", "月报"])

    def test_schema_validation_normalizes_create_field(self) -> None:
        context = _schema_validation_context(
            [{"action": "create_field", "field_name": "情绪", "field_type": "text", "property": {}, "reason": "记录心情"}],
            "新增字段 情绪",
        )

        with patch.object(validation, "load_config", return_value=FakeConfig()):
            output = validation.run_validation_node(context)

        request = output["data_json"]["tool_input_payload"]["schema_change_request"]
        self.assertEqual(request["actions"][0]["type"], 1)
        self.assertEqual(output["data_json"]["preview"]["actions"][0]["field_name"], "情绪")

    def test_schema_validation_rejects_bad_actions(self) -> None:
        duplicate = _schema_validation_context([{"action": "create_field", "field_name": "标题", "field_type": "text"}], "新增字段 标题")
        type_change = _schema_validation_context([{"action": "update_field", "field_name": "标题", "field_type": "number"}], "把字段标题改成数字")
        missing_delete = _schema_validation_context([{"action": "delete_field", "field_name": "不存在"}], "删除字段 不存在")

        with patch.object(validation, "load_config", return_value=FakeConfig()):
            with self.assertRaisesRegex(ValueError, "已存在"):
                validation.run_validation_node(duplicate)
            with self.assertRaisesRegex(ValueError, "不支持修改字段类型"):
                validation.run_validation_node(type_change)
            with self.assertRaisesRegex(ValueError, "存在"):
                validation.run_validation_node(missing_delete)

    def test_schema_tool_changes_mock_fields(self) -> None:
        context = _schema_validation_context(
            [{"action": "create_field", "field_name": "情绪", "field_type": "text", "property": {}, "reason": "记录心情"}],
            "新增字段 情绪",
        )

        with patch.object(validation, "load_config", return_value=FakeConfig()):
            validated = validation.run_validation_node(context)
        payload = {"content": [{"text": json.dumps(validated["data_json"]["tool_input_payload"], ensure_ascii=False)}]}
        with patch.object(schema_tool, "load_config", return_value=FakeConfig()):
            result = schema_tool.run_tool_ChangeFeishuBitableFields(payload)

        data = json.loads(result["content"][0]["text"])
        field_names = [field["field_name"] for field in mock_repository.list_mock_field_definitions()]
        self.assertEqual(data["action_count"], 1)
        self.assertIn("情绪", field_names)

    def test_schema_plan_validator_rejects_missing_refresh_and_delete_risk(self) -> None:
        missing_refresh = build_plan_from_template("change_schema_then_create_record", "新增字段 情绪，然后写一条记录")
        missing_refresh["steps"] = [step for step in missing_refresh["steps"] if step.get("step_id") != "step_refresh_schema"]
        delete_risk = build_plan_from_template("change_schema", "删除字段 状态", risk_level="write")

        with self.assertRaisesRegex(PlanValidationError, "feishu.table_schema_after|refresh_schema"):
            validate_workflow_plan(missing_refresh, agent_prompts=AGENT_PROMPTS)
        with self.assertRaisesRegex(PlanValidationError, "risk_level=delete"):
            validate_workflow_plan(delete_risk, agent_prompts=AGENT_PROMPTS)


def _schema_validation_context(actions: list[dict[str, object]], original_input: str) -> dict[str, object]:
    return {
        "original_input": original_input,
        "artifacts": {
            "feishu.table_schema": {"data_json": {"table_fields": TABLE_FIELDS}},
            "feishu.schema_change_payload": {
                "data_json": {
                    "tool_name": "tool_ChangeFeishuBitableFields",
                    "operation": "change_fields",
                    "request_key": "schema_change_request",
                    "table_fields": TABLE_FIELDS,
                    "tool_input_payload": {
                        "schema_change_request": {
                            "operation": "change_fields",
                            "service": "feishu_bitable",
                            "actions": actions,
                        }
                    },
                }
            },
        },
    }


if __name__ == "__main__":
    unittest.main()
