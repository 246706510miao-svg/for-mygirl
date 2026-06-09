"""workflow content[0].text 工具函数。"""

from __future__ import annotations

import json
import re
from typing import Any


# 这个函数从统一 content 外壳中读取第一段 text。
def extract_content_text(payload: dict[str, Any]) -> str:
    content = payload.get("content") or []
    if content and isinstance(content, list):
        first = content[0] or {}
        if isinstance(first, dict):
            return str(first.get("text") or "").strip()
    return str(payload.get("text") or payload.get("input") or "").strip()


# 这个函数把文本包装成统一 content[0].text 输出。
def content(text: str) -> dict[str, list[dict[str, str]]]:
    return {"content": [{"text": text}]}


# 这个函数把对象序列化后包装进 content[0].text。
def json_content(payload: dict[str, Any]) -> dict[str, list[dict[str, str]]]:
    return content(json.dumps(payload, ensure_ascii=False, default=str))


# 这个函数解析 JSON 对象，兼容模型返回 Markdown 代码块。
def load_json_object(text: str) -> dict[str, Any] | None:
    cleaned = text.strip()
    if cleaned.startswith("```"):
        cleaned = re.sub(r"^```(?:json)?", "", cleaned).strip()
        cleaned = re.sub(r"```$", "", cleaned).strip()
    try:
        loaded = json.loads(cleaned)
    except json.JSONDecodeError:
        return None
    return loaded if isinstance(loaded, dict) else None
