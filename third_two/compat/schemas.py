"""兼容层请求模型；核心 TaskState 不依赖旧 API 命名。"""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field


class ContentPart(BaseModel):
    text: str = ""


class InvokeWorkflowRequest(BaseModel):
    content: list[ContentPart] = Field(default_factory=list)
    metadata: dict[str, Any] = Field(default_factory=dict)
    private_metadata: dict[str, Any] = Field(default_factory=dict, alias="privateMetadata")


class ResumeWorkflowRequest(BaseModel):
    confirmation_id: str
    approved: bool
    content: list[ContentPart] = Field(default_factory=list)


class FeishuTableCheckRequest(BaseModel):
    private_metadata: dict[str, Any] = Field(default_factory=dict, alias="privateMetadata")
