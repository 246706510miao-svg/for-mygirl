"""Workflow API 的请求和响应模型。"""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field


# 这个模型定义 content[0].text 的单段文本结构。
class ContentPart(BaseModel):
    text: str = ""


# 这个模型定义提交 workflow 的请求体。
class InvokeWorkflowRequest(BaseModel):
    content: list[ContentPart] = Field(default_factory=list)


# 这个模型定义恢复确认 workflow 的请求体。
class ResumeWorkflowRequest(BaseModel):
    confirmation_id: str
    approved: bool
    content: list[ContentPart] = Field(default_factory=list)


# 这个模型定义 workflow API 返回的统一结构。
class WorkflowResponse(BaseModel):
    session_id: str
    status: str
    confirmation: dict[str, Any] | None = None
    content: list[ContentPart] = Field(default_factory=list)
    error_text: str | None = None
