"""第三方服务模块的 LangGraph 状态定义。"""

from __future__ import annotations

from typing import Any, TypedDict


# 这个类型定义 LangGraph 节点之间传递的状态字段。
class ThirdServiceState(TypedDict, total=False):
    input: str
    route: dict[str, Any]
    read_request: dict[str, Any]
    read_result: dict[str, Any]
    output: str
    error: str
