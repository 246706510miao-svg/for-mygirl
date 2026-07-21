from __future__ import annotations

import unittest
from unittest.mock import patch

from third.Tool.feishu_client import FeishuBitableClient, FeishuClientError
from third.Tool.feishu_table_resolver import (
    FEISHU_URL_INVALID,
    FEISHU_WIKI_NOT_BITABLE,
    FEISHU_WIKI_PERMISSION_DENIED,
    FeishuTableResolveError,
    resolve_feishu_table_url,
)
from third.agents.shared.config import load_config, private_metadata_context


class FeishuTableResolverTests(unittest.TestCase):
    def _config(self):
        with patch.dict(
            "os.environ",
            {
                "THIRD_FEISHU_APP_ID": "cli_test",
                "THIRD_FEISHU_APP_SECRET": "secret_test",
                "THIRD_FEISHU_TENANT_ACCESS_TOKEN": "",
                "THIRD_FEISHU_USE_REAL": "0",
            },
            clear=False,
        ):
            return load_config()

    def test_base_url_and_query_aliases_resolve_without_remote_call(self) -> None:
        resolved = resolve_feishu_table_url(
            "https://example.larksuite.com/base/app_xxx?table_id=tbl_xxx&view_id=vew_xxx",
            self._config(),
        )

        self.assertEqual(resolved.source_type, "base")
        self.assertEqual(resolved.app_token, "app_xxx")
        self.assertEqual(resolved.table_id, "tbl_xxx")
        self.assertEqual(resolved.view_id, "vew_xxx")

    def test_wiki_url_uses_bitable_obj_token(self) -> None:
        with patch.object(
            FeishuBitableClient,
            "get_wiki_node",
            return_value={"obj_type": "bitable", "obj_token": "app_from_wiki"},
        ) as get_node:
            resolved = resolve_feishu_table_url(
                "https://example.feishu.cn/wiki/wik_xxx?table=tbl_xxx&view=vew_xxx",
                self._config(),
            )

        self.assertEqual(resolved.source_type, "wiki")
        self.assertEqual(resolved.app_token, "app_from_wiki")
        self.assertEqual(resolved.table_id, "tbl_xxx")
        get_node.assert_called_once_with("wik_xxx")

    def test_wiki_client_calls_the_official_node_endpoint_with_auth(self) -> None:
        client = FeishuBitableClient(self._config())
        with patch.object(
            client,
            "_get_json",
            return_value={"data": {"node": {"obj_type": "bitable", "obj_token": "app_xxx"}}},
        ) as get_json:
            node = client.get_wiki_node("wik_xxx")

        self.assertEqual(node["obj_token"], "app_xxx")
        get_json.assert_called_once_with(
            "https://open.feishu.cn/open-apis/wiki/v2/spaces/get_node?token=wik_xxx",
            with_auth=True,
        )

    def test_wiki_url_rejects_non_bitable_node(self) -> None:
        with patch.object(
            FeishuBitableClient,
            "get_wiki_node",
            return_value={"obj_type": "docx", "obj_token": "doc_xxx"},
        ):
            with self.assertRaises(FeishuTableResolveError) as raised:
                resolve_feishu_table_url(
                    "https://example.feishu.cn/wiki/wik_xxx?table=tbl_xxx",
                    self._config(),
                )

        self.assertEqual(raised.exception.error_code, FEISHU_WIKI_NOT_BITABLE)

    def test_wiki_permission_error_is_classified(self) -> None:
        with patch.object(
            FeishuBitableClient,
            "get_wiki_node",
            side_effect=FeishuClientError("飞书接口返回错误 code=131006, msg=permission denied"),
        ):
            with self.assertRaises(FeishuTableResolveError) as raised:
                resolve_feishu_table_url(
                    "https://example.feishu.cn/wiki/wik_xxx?table=tbl_xxx",
                    self._config(),
                )

        self.assertEqual(raised.exception.error_code, FEISHU_WIKI_PERMISSION_DENIED)

    def test_wiki_node_without_obj_token_is_rejected(self) -> None:
        with patch.object(
            FeishuBitableClient,
            "get_wiki_node",
            return_value={"obj_type": "bitable", "obj_token": ""},
        ):
            with self.assertRaises(FeishuTableResolveError) as raised:
                resolve_feishu_table_url(
                    "https://example.feishu.cn/wiki/wik_xxx?table=tbl_xxx",
                    self._config(),
                )

        self.assertEqual(raised.exception.error_code, "FEISHU_WIKI_RESOLVE_FAILED")

    def test_url_without_concrete_table_is_rejected(self) -> None:
        with self.assertRaises(FeishuTableResolveError) as raised:
            resolve_feishu_table_url("https://example.feishu.cn/base/app_xxx", self._config())

        self.assertEqual(raised.exception.error_code, FEISHU_URL_INVALID)

    def test_non_feishu_domain_is_rejected(self) -> None:
        with self.assertRaises(FeishuTableResolveError) as raised:
            resolve_feishu_table_url(
                "https://example.com/base/app_xxx?table=tbl_xxx",
                self._config(),
            )

        self.assertEqual(raised.exception.error_code, FEISHU_URL_INVALID)

    def test_account_only_private_metadata_loads_credentials_without_enabling_table(self) -> None:
        private_metadata = {
            "feishu": {
                "account": {
                    "enabled": True,
                    "app_id": "cli_private",
                    "app_secret": "private_secret",
                    "tenant_access_token": "",
                }
            }
        }
        with patch.dict("os.environ", {"THIRD_FEISHU_TENANT_ACCESS_TOKEN": "environment_token"}, clear=False):
            with private_metadata_context(private_metadata):
                config = load_config()

        self.assertEqual(config.feishu_app_id, "cli_private")
        self.assertEqual(config.feishu_app_secret, "private_secret")
        self.assertEqual(config.feishu_tenant_access_token, "")
        self.assertFalse(config.feishu_use_real)


if __name__ == "__main__":
    unittest.main()
