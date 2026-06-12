from __future__ import annotations

import json
import unittest
from unittest.mock import patch

from third.Tool import tool_CreateFeishuBitableRecord as create_tool
from third.workflow import executor
from third.workflow import tool_dispatcher
from third.workflow import validation
from third.workflow.plan_validator import validate_workflow_plan


class FakeConfig:
    feishu_use_real = False
    feishu_field_name_map: dict[str, str] = {}
    finagent_use_llm = False
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


class BatchCreateWorkflowTests(unittest.TestCase):
    def test_validation_normalizes_batch_create_records(self) -> None:
        context = {
            "original_input": "英语和个人项目各一个半小时，写到飞书里面",
            "artifacts": {
                "feishu.create_payload": {
                    "data_json": {
                        "tool_name": "tool_CreateFeishuBitableRecord",
                        "operation": "create_record",
                        "request_key": "create_request",
                        "table_fields": TABLE_FIELDS,
                        "tool_input_payload": {
                            "create_request": {
                                "records": [
                                    {"fields": {"事项名称": "英语学习", "用时": "1.5", "评级": "B"}},
                                    {"fields": {"事项名称": "个人项目跟进", "用时": "1.5", "评级": "B"}},
                                ]
                            }
                        },
                    }
                }
            },
        }

        with patch.object(validation, "load_config", return_value=FakeConfig()):
            output = validation.run_validation_node(context)

        data = output["data_json"]
        self.assertEqual(data["preview"]["record_count"], 2)
        records = data["tool_input_payload"]["create_request"]["records"]
        self.assertEqual([record["fields"]["事项名称"] for record in records], ["英语学习", "个人项目跟进"])
        self.assertEqual(records[0]["fields"]["用时"], 1.5)

    def test_create_tool_accepts_batch_create_records(self) -> None:
        payload = {
            "content": [
                {
                    "text": json.dumps(
                        {
                            "original_input": "批量新增",
                            "create_request": {
                                "records": [
                                    {"fields": {"事项名称": "英语学习", "用时": 1.5}},
                                    {"fields": {"事项名称": "个人项目跟进", "用时": 1.5}},
                                ]
                            },
                        },
                        ensure_ascii=False,
                    )
                }
            ]
        }

        with patch.object(create_tool, "load_config", return_value=FakeConfig()), patch.object(
            create_tool, "load_table_fields_context", return_value=TABLE_FIELDS
        ):
            result = create_tool.run_tool_CreateFeishuBitableRecord(payload)

        data = json.loads(result["content"][0]["text"])
        self.assertEqual(data["record_count"], 2)
        self.assertEqual(len(data["records"]), 2)

    def test_plan_validator_normalizes_string_final(self) -> None:
        plan = {
            "type": "workflow_plan",
            "version": "workflow.v1",
            "intent": "create_feishu_record",
            "risk_level": "write",
            "requires_confirmation": True,
            "original_input": "新增记录",
            "final": "飞书记录已成功创建",
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
                    "agent_name": "business_agent",
                    "prompt_ref": "parse_feishu_record.v1",
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

        validated = validate_workflow_plan(
            plan,
            agent_prompts=[{"prompt_key": "parse_feishu_record.v1", "agent_name": "business_agent"}],
        )

        self.assertEqual(validated["final"], {"source": "write_result", "format": "answer"})

    def test_validation_merges_search_agent_record_match_for_delete(self) -> None:
        context = {
            "original_input": "删除昨天英语那条",
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
                "feishu.record_match": {
                    "data_json": {
                        "matched_record": {
                            "record_id": "rec_1",
                            "confidence": 0.31,
                            "confidence_level": "low",
                            "reason": "英语关键词最接近",
                            "record_fields": {"事项名称": "英语学习"},
                            "alternative_records": [{"record_id": "rec_2", "fields": {"事项名称": "个人项目"}}],
                        }
                    }
                },
            },
        }

        with patch.object(validation, "load_config", return_value=FakeConfig()):
            output = validation.run_validation_node(context)

        data = output["data_json"]
        delete_request = data["tool_input_payload"]["delete_request"]
        self.assertEqual(delete_request["record_id"], "rec_1")
        self.assertEqual(data["preview"]["match_info"]["confidence_level"], "low")
        self.assertTrue(data["preview"]["match_info"]["requires_careful_review"])

    def test_confirmation_text_warns_for_low_confidence_match(self) -> None:
        text = executor._confirmation_request_text({"match_info": {"requires_careful_review": True}})

        self.assertIn("低置信匹配", text)

    def test_tool_dispatcher_reads_payload_from_artifact_path(self) -> None:
        context = {
            "original_input": "删除昨天英语那条",
            "step": {
                "tool_name": "tool_ReadFeishuBitable",
                "input_spec_json": {
                    "from_session": ["feishu.delete_payload"],
                    "tool_payload_from": {"artifact_key": "feishu.delete_payload", "path": "data_json.candidate_read_payload"},
                },
            },
            "artifacts": {
                "feishu.delete_payload": {
                    "data_json": {
                        "candidate_read_payload": {
                            "original_input": "删除昨天英语那条",
                            "read_request": {"operation": "search_records", "page_size": 50},
                        }
                    }
                }
            },
        }

        payload = tool_dispatcher._build_tool_payload(context)
        data = json.loads(payload["content"][0]["text"])

        self.assertEqual(data["read_request"]["page_size"], 50)

    def test_tool_dispatcher_falls_back_to_candidate_read_payload_for_read_tool(self) -> None:
        context = {
            "original_input": "删除昨天英语那条",
            "step": {
                "tool_name": "tool_ReadFeishuBitable",
                "input_spec_json": {"from_session": ["feishu.delete_payload"]},
            },
            "artifacts": {
                "feishu.delete_payload": {
                    "data_json": {
                        "candidate_read_payload": {
                            "original_input": "删除昨天英语那条",
                            "read_request": {"operation": "search_records", "page_size": 50},
                        },
                        "tool_input_payload": {"delete_request": {"lookup": {"filter": {"conditions": []}}}},
                    }
                }
            },
        }

        payload = tool_dispatcher._build_tool_payload(context)
        data = json.loads(payload["content"][0]["text"])

        self.assertEqual(data["read_request"]["operation"], "search_records")
        self.assertEqual(data["read_request"]["page_size"], 50)

    def test_tool_dispatcher_rejects_read_tool_payload_without_read_request(self) -> None:
        context = {
            "original_input": "删除昨天英语那条",
            "step": {
                "tool_name": "tool_ReadFeishuBitable",
                "input_spec_json": {
                    "from_session": ["feishu.delete_payload"],
                    "tool_payload_from": {"artifact_key": "feishu.delete_payload", "path": "data_json.tool_input_payload"},
                },
            },
            "artifacts": {
                "feishu.delete_payload": {
                    "data_json": {
                        "tool_input_payload": {"delete_request": {"lookup": {"filter": {"conditions": []}}}},
                    }
                }
            },
        }

        with self.assertRaisesRegex(ValueError, "缺少 read_request"):
            tool_dispatcher._build_tool_payload(context)

    def test_tool_dispatcher_reads_tool_input_payload_from_any_validation_artifact(self) -> None:
        context = {
            "original_input": "删除昨天英语那条",
            "step": {
                "tool_name": "tool_DeleteFeishuBitableRecord",
                "input_spec_json": {"from_session": ["validation.delete_payload"]},
            },
            "artifacts": {
                "validation.delete_payload": {
                    "data_json": {
                        "tool_input_payload": {
                            "original_input": "删除昨天英语那条",
                            "delete_request": {"record_id": "rec_1"},
                        }
                    }
                }
            },
        }

        payload = tool_dispatcher._build_tool_payload(context)
        data = json.loads(payload["content"][0]["text"])

        self.assertEqual(data["delete_request"]["record_id"], "rec_1")


if __name__ == "__main__":
    unittest.main()
