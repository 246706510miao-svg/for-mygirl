"""OpenAI client factory for third service agents."""

from __future__ import annotations

from typing import Any


# 这个函数集中创建 ChatOpenAI，确保 third 的 OpenAI 出口只由 ThirdServiceConfig 控制。
def create_chat_openai(config: Any, model: str, temperature: float = 0):
    from langchain_openai import ChatOpenAI

    kwargs: dict[str, Any] = {
        "model": model,
        "temperature": temperature,
        "api_key": getattr(config, "openai_api_key", ""),
        "request_timeout": getattr(config, "openai_timeout_seconds", 60),
        "max_retries": getattr(config, "openai_max_retries", 2),
    }
    proxy_url = str(getattr(config, "openai_proxy_url", "") or "").strip()
    if proxy_url:
        kwargs["openai_proxy"] = proxy_url
    return ChatOpenAI(**kwargs)
