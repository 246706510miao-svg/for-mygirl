"""OpenAI client factory for third service agents."""

from __future__ import annotations

from typing import Any

from .llm_routes import RouteAwareChatModel, create_provider_client, primary_provider_spec


# 这个函数集中创建 ChatOpenAI，确保 third 的 OpenAI 出口只由 ThirdServiceConfig 控制。
def create_chat_openai(config: Any, model: str, temperature: float = 0):
    primary_spec = primary_provider_spec(config, model)
    primary_client = create_provider_client(primary_spec, temperature=temperature) if primary_spec.ready else None
    return RouteAwareChatModel(config, model, temperature=temperature, primary_client=primary_client)
