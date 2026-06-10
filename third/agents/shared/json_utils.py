"""JSON 边界工具。"""

from __future__ import annotations

import json
from datetime import date, datetime
from typing import Any


# 这个函数把 Python 对象转换成可写入 JSON/Redis 的结构。
def to_jsonable(value: Any) -> Any:
    if isinstance(value, datetime):
        return value.isoformat()
    if isinstance(value, date):
        return value.isoformat()
    if isinstance(value, dict):
        return {str(to_jsonable(key)): to_jsonable(item) for key, item in value.items()}
    if isinstance(value, (list, tuple, set)):
        return [to_jsonable(item) for item in value]
    if value is None or isinstance(value, (str, int, float, bool)):
        return value
    return str(value)


# 这个函数统一生成 JSON 字符串，避免 Redis 写入时遇到 datetime 报错。
def dumps_json(value: Any, **kwargs: Any) -> str:
    kwargs.setdefault("ensure_ascii", False)
    return json.dumps(to_jsonable(value), **kwargs)
