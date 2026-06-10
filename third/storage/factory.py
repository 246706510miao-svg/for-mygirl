"""workflow Repository 工厂。"""

from __future__ import annotations

try:
    from ..agents.shared.config import load_config
except ImportError:
    from agents.shared.config import load_config

from .repository import InMemoryWorkflowRepository, SqlAlchemyWorkflowRepository, WorkflowRepository


# 这一段保存进程内内存 Repository，方便无 MySQL 的本地 mock 调试复用状态。
_MEMORY_REPOSITORY = InMemoryWorkflowRepository()


# 这个函数根据配置创建 Repository；没有 THIRD_MYSQL_DSN 时使用内存兜底。
def get_workflow_repository() -> WorkflowRepository:
    config = load_config()
    if not config.mysql_dsn:
        if not config.allow_in_memory_fallback:
            raise RuntimeError("未配置 THIRD_MYSQL_DSN，且 THIRD_ALLOW_IN_MEMORY_FALLBACK=0，无法使用内存 Repository。")
        return _MEMORY_REPOSITORY
    from .database import create_session_factory

    return SqlAlchemyWorkflowRepository(create_session_factory())
