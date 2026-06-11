from __future__ import annotations

import unittest

from third.Tool.write_support import build_write_request, normalize_write_request


class FakeConfig:
    def __init__(self, field_name_map: dict[str, str] | None = None) -> None:
        self.feishu_use_real = True
        self.feishu_field_name_map = field_name_map or {}

    @property
    def table_context(self) -> dict[str, str]:
        return {
            "app_token": "app_test",
            "table_id": "tbl_test",
            "table_name": "test",
            "view_id": "vew_test",
            "user_id_type": "open_id",
        }


TABLE_FIELDS = {
    "source": "feishu",
    "table_name": "test",
    "field_names": ["评级", "用时", "总结", "日期", "事项名称"],
    "fields": [
        {"field_name": "评级", "type": 3, "property": {}},
        {"field_name": "用时", "type": 2, "property": {}},
        {"field_name": "总结", "type": 1, "property": {}},
        {"field_name": "日期", "type": 5, "property": {}},
        {"field_name": "事项名称", "type": 1, "property": {}},
    ],
}


class WriteSupportFieldExtractionTests(unittest.TestCase):
    def test_real_field_name_does_not_add_unresolved_alias_field(self) -> None:
        config = FakeConfig()
        user_input = "新增一条记录，事项名称为排查 agent 格式，总结为结构化输出测试，评级为A，用时为1.5，日期为2026-06-10"

        request = build_write_request("create_record", user_input, config, TABLE_FIELDS)
        normalized = normalize_write_request("create_record", request, user_input, config, TABLE_FIELDS, require_fields=True)

        self.assertNotIn("标题", request["fields"])
        self.assertNotIn("标题", normalized["fields"])
        self.assertEqual(normalized["validation_errors"], [])
        self.assertEqual(normalized["fields"]["事项名称"], "排查 agent 格式")
        self.assertEqual(normalized["fields"]["总结"], "结构化输出测试")
        self.assertEqual(normalized["fields"]["评级"], "A")
        self.assertEqual(normalized["fields"]["用时"], 1.5)
        self.assertIsInstance(normalized["fields"]["日期"], int)

    def test_explicit_field_name_map_can_still_map_alias_to_real_field(self) -> None:
        config = FakeConfig({"标题": "事项名称"})
        user_input = "新增一条记录，标题为排查 agent 格式"

        request = build_write_request("create_record", user_input, config, TABLE_FIELDS)

        self.assertEqual(request["fields"], {"事项名称": "排查 agent 格式"})


if __name__ == "__main__":
    unittest.main()
