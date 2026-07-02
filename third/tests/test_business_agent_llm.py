from __future__ import annotations

import json
import unittest
from types import SimpleNamespace
from unittest.mock import patch

from third.workflow import agent_runner


TABLE_FIELDS = {
    "source": "feishu",
    "table_name": "test",
    "field_names": ["评级", "用时", "总结", "日期", "事项名称"],
    "fields": [
        {"field_name": "评级", "type": 3, "property": {"options": [{"name": "A"}, {"name": "B"}]}},
        {"field_name": "用时", "type": 2, "property": {}},
        {"field_name": "总结", "type": 1, "property": {}},
        {"field_name": "日期", "type": 5, "property": {}},
        {"field_name": "事项名称", "type": 1, "property": {}},
    ],
}


class FakePromptRepository:
    def __init__(self, prompt: dict[str, object] | None = None) -> None:
        self.prompt = prompt

    def get_prompt(self, _: str) -> dict[str, object] | None:
        return self.prompt


def fake_config(use_llm: bool = True, api_key: str = "sk-test") -> SimpleNamespace:
    return SimpleNamespace(
        workflowagent_use_llm=use_llm,
        workflowagent_model="gpt-test",
        openai_api_key=api_key,
        feishu_use_real=True,
        feishu_field_name_map={},
        table_context={
            "app_token": "app_test",
            "table_id": "tbl_test",
            "table_name": "test",
            "view_id": "vew_test",
            "user_id_type": "open_id",
        },
    )


DEFAULT_PROMPT = {
    "prompt_key": "parse_feishu_record.v1",
    "agent_name": "business_agent",
    "role_name": "business_agent",
    "description": "parse feishu payload",
    "db_address": "prompt_registry.prompt_key=parse_feishu_record.v1",
    "input_schema_json": {},
    "prompt_text": "database prompt",
    "output_schema_json": {"source": "database"},
    "metadata_json": {},
    "version": "db",
    "enabled": True,
}

SEARCH_PROMPT = {
    "prompt_key": "search_feishu_record.v1",
    "agent_name": "search_agent",
    "role_name": "search_agent",
    "description": "match record",
    "db_address": "prompt_registry.prompt_key=search_feishu_record.v1",
    "input_schema_json": {},
    "prompt_text": "search prompt",
    "output_schema_json": {"source": "database"},
    "metadata_json": {},
    "version": "db",
    "enabled": True,
}


def business_context(repository: FakePromptRepository | None = None, intent: str = "create_feishu_record") -> dict[str, object]:
    return {
        "original_input": "新增一条记录，事项名称为排查 agent，评级为A",
        "plan": {"intent": intent},
        "step": {"prompt_ref": "parse_feishu_record.v1"},
        "artifacts": {"feishu.table_schema": {"data_json": {"table_fields": TABLE_FIELDS}}},
        "repository": repository or FakePromptRepository(DEFAULT_PROMPT),
    }


def search_context(repository: FakePromptRepository | None = None) -> dict[str, object]:
    return {
        "original_input": "删除昨天英语那条",
        "plan": {"intent": "delete_feishu_record"},
        "step": {"prompt_ref": "search_feishu_record.v1"},
        "artifacts": {
            "feishu.delete_payload": {
                "data_json": {
                    "tool_name": "tool_DeleteFeishuBitableRecord",
                    "operation": "delete_record",
                    "request_key": "delete_request",
                    "table_fields": TABLE_FIELDS,
                    "tool_input_payload": {
                        "delete_request": {
                            "operation": "delete_record",
                            "service": "feishu_bitable",
                            "lookup": {"filter": {"conjunction": "and", "conditions": []}},
                        }
                    },
                }
            },
            "feishu.candidate_records": {
                "data_json": {
                    "records": [
                        {"record_id": "rec_1", "fields": {"事项名称": "英语学习", "总结": "昨天背单词"}},
                        {"record_id": "rec_2", "fields": {"事项名称": "个人项目", "总结": "修复 agent"}},
                    ]
                }
            },
        },
        "repository": repository or FakePromptRepository(SEARCH_PROMPT),
    }


class BusinessAgentLlmTests(unittest.TestCase):
    def test_load_prompt_prefers_repository_prompt(self) -> None:
        repository = FakePromptRepository(
            {
                "prompt_key": "parse_feishu_record.v1",
                "agent_name": "business_agent",
                "role_name": "business_agent",
                "prompt_text": "database prompt",
                "output_schema_json": {"source": "database"},
                "version": "db",
                "enabled": True,
            }
        )

        prompt = agent_runner._load_business_prompt("parse_feishu_record.v1", {"repository": repository})

        self.assertEqual(prompt["prompt_text"], "database prompt")
        self.assertEqual(prompt["output_schema_json"], {"source": "database"})

    def test_load_prompt_requires_database_prompt(self) -> None:
        with self.assertRaisesRegex(RuntimeError, "prompt_registry"):
            agent_runner._load_business_prompt("parse_feishu_record.v1", {"repository": FakePromptRepository()})

    def test_unsupported_prompt_ref_fails(self) -> None:
        context = business_context()
        context["step"] = {"prompt_ref": "unknown.v1"}

        with self.assertRaisesRegex(ValueError, "暂不支持"):
            agent_runner.run_business_agent(context)

    def test_llm_parse_success_returns_current_artifact_shape(self) -> None:
        response = json.dumps(
            {
                "create_request": {
                    "operation": "create_record",
                    "service": "feishu_bitable",
                    "fields": {"事项名称": "排查 agent", "评级": "A"},
                }
            },
            ensure_ascii=False,
        )
        with patch.object(agent_runner, "load_config", return_value=fake_config()), patch.object(
            agent_runner, "_invoke_business_agent_model", return_value=response
        ):
            output = agent_runner.run_business_agent(business_context())

        data_json = output["data_json"]
        self.assertEqual(data_json["source"], "llm")
        self.assertEqual(data_json["request_key"], "create_request")
        self.assertEqual(
            data_json["tool_input_payload"]["create_request"]["fields"],
            {"事项名称": "排查 agent", "评级": "A"},
        )

    def test_llm_parse_accepts_batch_create_records(self) -> None:
        response = json.dumps(
            {
                "create_request": {
                    "records": [
                        {"fields": {"事项名称": "英语学习", "用时": "1.5", "评级": "B"}},
                        {"fields": {"事项名称": "个人项目跟进", "用时": "1.5", "评级": "B"}},
                    ]
                }
            },
            ensure_ascii=False,
        )
        with patch.object(agent_runner, "load_config", return_value=fake_config()), patch.object(
            agent_runner, "_invoke_business_agent_model", return_value=response
        ):
            output = agent_runner.run_business_agent(business_context())

        records = output["data_json"]["tool_input_payload"]["create_request"]["records"]
        self.assertEqual([record["fields"]["事项名称"] for record in records], ["英语学习", "个人项目跟进"])

    def test_llm_parse_update_outputs_candidate_read_payload(self) -> None:
        response = json.dumps(
            {
                "update_request": {
                    "fields": {"评级": "A"},
                    "lookup": {"filter": {"conjunction": "and", "conditions": [{"field_name": "事项名称", "operator": "contains", "value": "英语"}]}},
                }
            },
            ensure_ascii=False,
        )
        with patch.object(agent_runner, "load_config", return_value=fake_config()), patch.object(
            agent_runner, "_invoke_business_agent_model", return_value=response
        ):
            output = agent_runner.run_business_agent(business_context(intent="update_feishu_record"))

        candidate_payload = output["data_json"]["candidate_read_payload"]
        self.assertEqual(candidate_payload["read_request"]["operation"], "search_records")
        self.assertEqual(candidate_payload["read_request"]["page_size"], 50)
        self.assertEqual(candidate_payload["read_request"]["filter"]["conditions"][0]["field_name"], "事项名称")

    def test_llm_prompt_includes_current_date(self) -> None:
        prompt = agent_runner._build_llm_prompt("prompt", "今天写到飞书", "create_record", "create_request", TABLE_FIELDS, {})

        self.assertIn("current_date", prompt)
        self.assertIn("current_datetime", prompt)

    def test_llm_mode_requires_any_llm_provider(self) -> None:
        with patch.object(agent_runner, "load_config", return_value=fake_config(api_key="")):
            with self.assertRaisesRegex(RuntimeError, "可用 LLM provider"):
                agent_runner.run_business_agent(business_context())

    def test_llm_mode_rejects_invalid_json(self) -> None:
        with patch.object(agent_runner, "load_config", return_value=fake_config()), patch.object(
            agent_runner, "_invoke_business_agent_model", return_value="不是 JSON"
        ):
            with self.assertRaisesRegex(ValueError, "合法 JSON"):
                agent_runner.run_business_agent(business_context())

    def test_llm_mode_requires_expected_request_key(self) -> None:
        with patch.object(agent_runner, "load_config", return_value=fake_config()), patch.object(
            agent_runner, "_invoke_business_agent_model", return_value=json.dumps({"wrong_request": {}})
        ):
            with self.assertRaisesRegex(ValueError, "create_request"):
                agent_runner.run_business_agent(business_context())

    def test_search_agent_llm_success_returns_match_artifact(self) -> None:
        response = json.dumps(
            {
                "matched_record": {
                    "record_id": "rec_1",
                    "confidence": 0.42,
                    "confidence_level": "low",
                    "reason": "用户提到英语",
                    "record_fields": {"事项名称": "英语学习"},
                    "alternative_records": [{"record_id": "rec_2", "fields": {"事项名称": "个人项目"}}],
                }
            },
            ensure_ascii=False,
        )
        with patch.object(agent_runner, "load_config", return_value=fake_config()), patch.object(
            agent_runner, "_invoke_business_agent_model", return_value=response
        ):
            output = agent_runner.run_business_agent(search_context())

        matched_record = output["data_json"]["matched_record"]
        self.assertEqual(matched_record["record_id"], "rec_1")
        self.assertEqual(matched_record["confidence_level"], "low")

    def test_search_agent_requires_candidate_records(self) -> None:
        context = search_context()
        context["artifacts"]["feishu.candidate_records"] = {"data_json": {"records": []}}

        with patch.object(agent_runner, "load_config", return_value=fake_config()):
            with self.assertRaisesRegex(ValueError, "候选记录"):
                agent_runner.run_business_agent(context)

    def test_search_agent_rejects_missing_record_id(self) -> None:
        with patch.object(agent_runner, "load_config", return_value=fake_config()), patch.object(
            agent_runner, "_invoke_business_agent_model", return_value=json.dumps({"matched_record": {"confidence": 0.1}})
        ):
            with self.assertRaisesRegex(ValueError, "record_id"):
                agent_runner.run_business_agent(search_context())

    def test_search_agent_rejects_record_id_outside_candidates(self) -> None:
        response = json.dumps(
            {
                "matched_record": {
                    "record_id": "rec_not_from_candidates",
                    "confidence": 0.9,
                    "confidence_level": "high",
                    "reason": "模型误选了不存在的候选 id",
                    "record_fields": {"事项名称": "英语学习"},
                    "alternative_records": [],
                }
            },
            ensure_ascii=False,
        )

        with patch.object(agent_runner, "load_config", return_value=fake_config()), patch.object(
            agent_runner, "_invoke_business_agent_model", return_value=response
        ):
            with self.assertRaisesRegex(ValueError, "候选记录"):
                agent_runner.run_business_agent(search_context())

    def test_rule_mode_keeps_existing_parser(self) -> None:
        with patch.object(agent_runner, "load_config", return_value=fake_config(use_llm=False)):
            output = agent_runner.run_business_agent(business_context())

        data_json = output["data_json"]
        self.assertEqual(data_json["source"], "rule")
        self.assertEqual(data_json["tool_input_payload"]["create_request"]["fields"]["事项名称"], "排查 agent")


if __name__ == "__main__":
    unittest.main()
