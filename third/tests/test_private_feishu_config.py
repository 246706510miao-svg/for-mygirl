from __future__ import annotations

import os
import unittest
from unittest.mock import patch

from third.agents.shared.config import load_config, private_metadata_context


class PrivateFeishuConfigTests(unittest.TestCase):
    def test_private_metadata_overrides_environment_feishu_table(self) -> None:
        private_metadata = {
            "feishu": {
                "account": {
                    "enabled": True,
                    "app_id": "cli_private",
                    "app_secret": "private-secret",
                    "tenant_access_token": "",
                    "user_id_type": "open_id",
                },
                "table": {
                    "enabled": True,
                    "display_name": "用户表",
                    "app_token": "app_private",
                    "table_id": "tbl_private",
                    "view_id": "vew_private",
                    "field_name_map": {"summary": "总结"},
                },
            }
        }
        env = {
            "THIRD_FEISHU_USE_REAL": "0",
            "THIRD_FEISHU_APP_ID": "cli_env",
            "THIRD_FEISHU_APP_SECRET": "env-secret",
            "THIRD_FEISHU_APP_TOKEN": "app_env",
            "THIRD_FEISHU_TABLE_ID": "tbl_env",
            "THIRD_FEISHU_TABLE_NAME": "环境表",
            "THIRD_FEISHU_FIELD_NAME_MAP": '{"summary":"环境总结"}',
        }

        with patch.dict(os.environ, env, clear=False), private_metadata_context(private_metadata):
            config = load_config()

        self.assertTrue(config.feishu_use_real)
        self.assertEqual(config.feishu_app_id, "cli_private")
        self.assertEqual(config.feishu_app_secret, "private-secret")
        self.assertEqual(config.feishu_app_token, "app_private")
        self.assertEqual(config.feishu_table_id, "tbl_private")
        self.assertEqual(config.feishu_table_name, "用户表")
        self.assertEqual(config.feishu_view_id, "vew_private")
        self.assertEqual(config.feishu_field_name_map, {"summary": "总结"})


if __name__ == "__main__":
    unittest.main()
