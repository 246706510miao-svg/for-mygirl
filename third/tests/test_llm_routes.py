from __future__ import annotations

import unittest
from types import SimpleNamespace
from unittest.mock import Mock, patch

from fastapi import HTTPException

from third.agents.shared.llm_routes import (
    LlmProviderSpec,
    classify_llm_exception,
    clear_probe_cache,
    create_provider_client,
    mark_provider_unhealthy,
    primary_provider_spec,
    probe_provider,
)
from third.agents.shared.openai_client import create_chat_openai
from third.debug import router as debug_router


class LlmRouteTests(unittest.TestCase):
    def setUp(self) -> None:
        clear_probe_cache()

    def tearDown(self) -> None:
        clear_probe_cache()

    def test_domestic_provider_uses_no_proxy_http_client(self) -> None:
        spec = LlmProviderSpec(
            name="deepseek",
            model="deepseek-chat",
            api_key="ds-test",
            base_url="https://api.deepseek.example/v1",
            proxy_url="http://proxy.example:3128",
            timeout_seconds=30,
            max_retries=1,
            no_proxy=True,
        )
        http_client = object()

        with patch("langchain_openai.ChatOpenAI") as chat_openai, patch("httpx.Client", return_value=http_client) as httpx_client:
            create_provider_client(spec, temperature=0.2)

        kwargs = chat_openai.call_args.kwargs
        self.assertEqual(kwargs["model"], "deepseek-chat")
        self.assertEqual(kwargs["base_url"], "https://api.deepseek.example/v1")
        self.assertEqual(kwargs["http_client"], http_client)
        self.assertNotIn("openai_proxy", kwargs)
        httpx_client.assert_called_once_with(trust_env=False)

    def test_primary_success_does_not_construct_fallback_client(self) -> None:
        config = _config(llm_probe_enabled=False)
        primary_client = Mock()
        primary_client.invoke.return_value = SimpleNamespace(content="ok")

        with patch("langchain_openai.ChatOpenAI", return_value=primary_client) as chat_openai:
            model = create_chat_openai(config, "gpt-test")
            response = model.invoke("hello")

        self.assertEqual(response.content, "ok")
        self.assertEqual(chat_openai.call_count, 1)
        primary_client.invoke.assert_called_once_with("hello")

    def test_primary_connection_failure_uses_deepseek_before_minimax(self) -> None:
        config = _config(llm_probe_enabled=False)
        primary_client = Mock()
        primary_client.invoke.side_effect = OSError("proxy connect failed")
        deepseek_client = Mock()
        deepseek_client.invoke.return_value = SimpleNamespace(content="fallback ok")

        with patch("langchain_openai.ChatOpenAI", side_effect=[primary_client, deepseek_client]) as chat_openai:
            with patch("httpx.Client", return_value=object()):
                model = create_chat_openai(config, "gpt-test")
                response = model.invoke("hello")

        self.assertEqual(response.content, "fallback ok")
        self.assertEqual(chat_openai.call_count, 2)
        fallback_kwargs = chat_openai.call_args.kwargs
        self.assertEqual(fallback_kwargs["model"], "deepseek-chat")
        self.assertNotIn("openai_proxy", fallback_kwargs)

    def test_domestic_mode_uses_deepseek_without_openai_key(self) -> None:
        config = _config(openai_api_key="", llm_route_mode="domestic", llm_probe_enabled=True)
        deepseek_client = Mock()
        deepseek_client.invoke.return_value = SimpleNamespace(content="domestic ok")

        with patch("langchain_openai.ChatOpenAI", return_value=deepseek_client) as chat_openai:
            with patch("httpx.Client", return_value=object()):
                model = create_chat_openai(config, "gpt-test")
                response = model.invoke("hello")

        self.assertEqual(response.content, "domestic ok")
        self.assertEqual(chat_openai.call_count, 1)
        self.assertEqual(chat_openai.call_args.kwargs["model"], "deepseek-chat")
        self.assertNotIn("openai_proxy", chat_openai.call_args.kwargs)

    def test_cached_unhealthy_primary_skips_primary_invoke(self) -> None:
        config = _config(llm_probe_enabled=True)
        mark_provider_unhealthy(config, primary_provider_spec(config, "gpt-test"), "connection_error", OSError("proxy failed"))
        primary_client = Mock()
        deepseek_client = Mock()
        deepseek_client.invoke.return_value = SimpleNamespace(content="fallback ok")

        with patch("langchain_openai.ChatOpenAI", side_effect=[primary_client, deepseek_client]):
            with patch("httpx.Client", return_value=object()):
                model = create_chat_openai(config, "gpt-test")
                response = model.invoke("hello")

        self.assertEqual(response.content, "fallback ok")
        primary_client.invoke.assert_not_called()
        deepseek_client.invoke.assert_called_once_with("hello")

    def test_unhealthy_primary_error_reports_fallback_timeout_detail(self) -> None:
        config = _config(llm_probe_enabled=True, llm_fallback_providers=["deepseek"])
        mark_provider_unhealthy(config, primary_provider_spec(config, "gpt-test"), "connection_error", OSError("proxy failed"))
        primary_client = Mock()
        deepseek_client = Mock()
        deepseek_client.invoke.side_effect = TimeoutError("read timed out after 30s")

        with patch("langchain_openai.ChatOpenAI", side_effect=[primary_client, deepseek_client]):
            with patch("httpx.Client", return_value=object()):
                model = create_chat_openai(config, "gpt-test")
                with self.assertRaisesRegex(RuntimeError, "deepseek: timeout"):
                    model.invoke("hello")

        primary_client.invoke.assert_not_called()

    def test_probe_provider_uses_success_threshold(self) -> None:
        config = _config(llm_probe_samples=3, llm_probe_min_successes=2)
        spec = primary_provider_spec(config, "gpt-test")
        clients = [
            _ProbeClient(content='{"status":"ok","source":"third_llm_probe"}'),
            _ProbeClient(error=OSError("temporary connection failed")),
            _ProbeClient(content='{"status":"ok","source":"third_llm_probe"}'),
        ]

        with patch("third.agents.shared.llm_routes.create_provider_client", side_effect=clients):
            result = probe_provider(spec, config, samples=3)

        self.assertEqual(result.status, "healthy")
        self.assertEqual(result.successes, 2)
        self.assertEqual(result.samples, 3)

    def test_probe_provider_classifies_auth_error(self) -> None:
        config = _config(llm_probe_samples=1, llm_probe_min_successes=1)
        spec = primary_provider_spec(config, "gpt-test")

        with patch("third.agents.shared.llm_routes.create_provider_client", return_value=_ProbeClient(error=_StatusError(401, "bad key"))):
            result = probe_provider(spec, config, samples=1)

        self.assertEqual(result.status, "auth_error")
        self.assertEqual(result.error_type, "auth_error")

    def test_debug_probe_endpoint_requires_debug_enabled(self) -> None:
        with patch.object(debug_router, "load_config", return_value=_config(debug_enabled=False)):
            with self.assertRaises(HTTPException) as raised:
                debug_router.debug_llm_routes_probe()

        self.assertEqual(raised.exception.status_code, 404)

    def test_status_code_5xx_is_fallback_eligible_server_error(self) -> None:
        self.assertEqual(classify_llm_exception(_StatusError(503, "upstream unavailable")), "server_error")


class _ProbeClient:
    def __init__(self, content: str = "", error: Exception | None = None) -> None:
        self.content = content
        self.error = error

    def invoke(self, prompt: str) -> SimpleNamespace:
        if self.error:
            raise self.error
        return SimpleNamespace(content=self.content)


class _StatusError(Exception):
    def __init__(self, status_code: int, message: str) -> None:
        super().__init__(message)
        self.status_code = status_code


def _config(**overrides):
    values = {
        "openai_api_key": "sk-test",
        "openai_proxy_url": "http://user:pass@jp.example.com:3128",
        "openai_timeout_seconds": 60,
        "openai_max_retries": 2,
        "workflowagent_model": "gpt-test",
        "llm_route_mode": "auto",
        "llm_fallback_providers": ["deepseek", "minimax"],
        "llm_probe_enabled": True,
        "llm_probe_ttl_seconds": 60,
        "llm_probe_samples": 3,
        "llm_probe_min_successes": 2,
        "llm_unhealthy_ttl_seconds": 120,
        "deepseek_api_key": "ds-test",
        "deepseek_base_url": "https://api.deepseek.example/v1",
        "deepseek_model": "deepseek-chat",
        "deepseek_timeout_seconds": 60,
        "deepseek_max_retries": 0,
        "minimax_api_key": "mm-test",
        "minimax_base_url": "https://api.minimax.example/v1",
        "minimax_model": "minimax-text",
        "minimax_timeout_seconds": 60,
        "minimax_max_retries": 0,
        "debug_enabled": True,
    }
    values.update(overrides)
    return SimpleNamespace(**values)


if __name__ == "__main__":
    unittest.main()
