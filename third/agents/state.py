"""第三方服务模块的 LangGraph 状态定义。"""

from __future__ import annotations

from typing import TypedDict


# 这个类型定义 content 的单段文本结构，当前只使用 content[0].text。
class ContentPart(TypedDict, total=False):
    text: str


# 这个类型定义 LangGraph 节点之间传递的状态字段，公开输入输出都只关注 content。
class ThirdServiceState(TypedDict, total=False):
    content: list[ContentPart]
