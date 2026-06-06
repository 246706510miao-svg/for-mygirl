"""第三方服务模块的时间工具。"""

from __future__ import annotations

from datetime import datetime


# 这个函数生成秒级 ISO 时间，用于路由和读取结果的可追踪字段。
def now_iso() -> str:
    return datetime.now().replace(microsecond=0).isoformat()

