"""Workflow capability registries."""

from __future__ import annotations

from .agents import build_agent_catalog
from .templates import TEMPLATE_CATALOG, build_plan_from_template
from .tools import (
    ALLOWED_TOOLS,
    CHANGE_SCHEMA_TOOL,
    CREATE_TOOL,
    DELETE_TOOL,
    READ_SCHEMA_TOOL,
    READ_TOOL,
    TOOL_CATALOG,
    UPDATE_TOOL,
    WRITE_TOOLS,
)

__all__ = [
    "ALLOWED_TOOLS",
    "CHANGE_SCHEMA_TOOL",
    "CREATE_TOOL",
    "DELETE_TOOL",
    "READ_SCHEMA_TOOL",
    "READ_TOOL",
    "TEMPLATE_CATALOG",
    "TOOL_CATALOG",
    "UPDATE_TOOL",
    "WRITE_TOOLS",
    "build_agent_catalog",
    "build_plan_from_template",
]
