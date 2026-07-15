from __future__ import annotations

import os
import unittest
from types import SimpleNamespace
from unittest.mock import patch

from third.agents.shared import config as config_module
from third.agents.shared.openai_client import create_chat_openai
from third.workflow import executor


class OpenAIClientConfigTests(unittest.TestCase):
    def test_load_config_reads_openai_outlet_settings(self) -> None:
        env = {
            "OPENAI_API_KEY": "sk-test",
            "THIRD_OPENAI_PROXY_URL": "http://user:pass@jp.example.com:3128",
            "THIRD_NEWS_FOCUS_PROXY_URL": "http://host.docker.internal:7891",
            "THIRD_OPENAI_TIMEOUT_SECONDS": "45",
            "THIRD_OPENAI_MAX_RETRIES": "4",
            "THIRD_LLM_ROUTE_MODE": "auto",
            "THIRD_LLM_FALLBACK_PROVIDERS": "deepseek,minimax",
            "THIRD_LLM_PROBE_ENABLED": "1",
            "THIRD_LLM_PROBE_TTL_SECONDS": "90",
            "THIRD_LLM_PROBE_SAMPLES": "5",
            "THIRD_LLM_PROBE_MIN_SUCCESSES": "3",
            "THIRD_LLM_UNHEALTHY_TTL_SECONDS": "180",
            "THIRD_DEEPSEEK_API_KEY": "ds-test",
            "THIRD_DEEPSEEK_BASE_URL": "https://api.deepseek.example/v1",
            "THIRD_DEEPSEEK_MODEL": "deepseek-chat",
            "THIRD_DEEPSEEK_TIMEOUT_SECONDS": "35",
            "THIRD_DEEPSEEK_MAX_RETRIES": "1",
            "THIRD_MINIMAX_API_KEY": "mm-test",
            "THIRD_MINIMAX_BASE_URL": "https://api.minimax.example/v1",
            "THIRD_MINIMAX_MODEL": "minimax-text",
        }

        with patch.dict(os.environ, env, clear=True), patch.object(config_module, "_load_env_files", return_value=None):
            config = config_module.load_config()

        self.assertEqual(config.openai_api_key, "sk-test")
        self.assertEqual(config.openai_proxy_url, "http://user:pass@jp.example.com:3128")
        self.assertEqual(config.news_focus_proxy_url, "http://host.docker.internal:7891")
        self.assertEqual(config.openai_timeout_seconds, 45)
        self.assertEqual(config.openai_max_retries, 4)
        self.assertEqual(config.llm_route_mode, "auto")
        self.assertEqual(config.llm_fallback_providers, ["deepseek", "minimax"])
        self.assertTrue(config.llm_probe_enabled)
        self.assertEqual(config.llm_probe_ttl_seconds, 90)
        self.assertEqual(config.llm_probe_samples, 5)
        self.assertEqual(config.llm_probe_min_successes, 3)
        self.assertEqual(config.llm_unhealthy_ttl_seconds, 180)
        self.assertTrue(config.deepseek_ready)
        self.assertTrue(config.minimax_ready)

    def test_create_chat_openai_omits_empty_proxy(self) -> None:
        config = SimpleNamespace(
            openai_api_key="sk-test",
            openai_proxy_url="",
            openai_timeout_seconds=60,
            openai_max_retries=2,
        )

        with patch("langchain_openai.ChatOpenAI") as chat_openai:
            create_chat_openai(config, "gpt-test", temperature=0.3)

        kwargs = chat_openai.call_args.kwargs
        self.assertEqual(kwargs["model"], "gpt-test")
        self.assertEqual(kwargs["temperature"], 0.3)
        self.assertEqual(kwargs["api_key"], "sk-test")
        self.assertEqual(kwargs["request_timeout"], 60)
        self.assertEqual(kwargs["max_retries"], 2)
        self.assertNotIn("openai_proxy", kwargs)

    def test_create_chat_openai_passes_configured_proxy(self) -> None:
        config = SimpleNamespace(
            openai_api_key="sk-test",
            openai_proxy_url="http://user:pass@jp.example.com:3128",
            openai_timeout_seconds=60,
            openai_max_retries=2,
        )

        with patch("langchain_openai.ChatOpenAI") as chat_openai:
            create_chat_openai(config, "gpt-test")

        self.assertEqual(chat_openai.call_args.kwargs["openai_proxy"], "http://user:pass@jp.example.com:3128")

    def test_openai_proxy_is_redacted_in_logs(self) -> None:
        redacted = executor._redact_text("THIRD_OPENAI_PROXY_URL=http://user:pass@jp.example.com:3128")

        self.assertNotIn("user:pass", redacted)
        self.assertEqual(redacted, "THIRD_OPENAI_PROXY_URL=***")

    def test_openai_proxy_url_credentials_are_redacted_without_key_name(self) -> None:
        redacted = executor._redact_text("proxy failed: http://user:pass@jp.example.com:3128")

        self.assertNotIn("user:pass", redacted)
        self.assertIn("http://***:***@jp.example.com:3128", redacted)

    def test_openai_proxy_key_is_redacted_in_structured_log_payload(self) -> None:
        redacted = executor._redact_for_log({"THIRD_OPENAI_PROXY_URL": "http://user:pass@jp.example.com:3128"})

        self.assertEqual(redacted["THIRD_OPENAI_PROXY_URL"], "***")

    def test_news_focus_proxy_is_redacted_in_logs(self) -> None:
        redacted = executor._redact_text("THIRD_NEWS_FOCUS_PROXY_URL=http://host.docker.internal:7891")

        self.assertEqual(redacted, "THIRD_NEWS_FOCUS_PROXY_URL=***")

    def test_domestic_llm_keys_are_redacted(self) -> None:
        redacted = executor._redact_text(
            "THIRD_DEEPSEEK_API_KEY=ds-secret THIRD_MINIMAX_BASE_URL=https://api.minimax.example/v1"
        )

        self.assertNotIn("ds-secret", redacted)
        self.assertNotIn("api.minimax.example", redacted)


if __name__ == "__main__":
    unittest.main()
