"""Agent capability catalog helpers."""

from __future__ import annotations

from typing import Any


# 这个函数把业务 prompt 整理成 workflowagent 可用的 catalog。
def build_agent_catalog(agent_prompts: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [
        {
            "agent_name": prompt.get("agent_name"),
            "prompt_ref": prompt.get("prompt_key"),
            "prompt_key": prompt.get("prompt_key"),
            "role_name": prompt.get("role_name"),
            "description": prompt.get("description"),
            "db_address": prompt.get("db_address"),
            "input_schema_json": prompt.get("input_schema_json") or {},
            "output_schema_json": prompt.get("output_schema_json") or {},
            "metadata_json": prompt.get("metadata_json") or {},
            "version": prompt.get("version"),
            "enabled": prompt.get("enabled", True),
        }
        for prompt in agent_prompts
        if prompt.get("enabled", True)
    ]
