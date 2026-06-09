"""workflow 运行态工厂。"""

from __future__ import annotations

try:
    from ..agents.shared.config import load_config
except ImportError:
    from agents.shared.config import load_config

from .redis_runtime import InMemoryWorkflowRuntimeStore, RedisWorkflowRuntimeStore, WorkflowRuntimeStore


# 这一段保存进程内内存运行态，方便无 Redis 的 mock 调试。
_MEMORY_RUNTIME = InMemoryWorkflowRuntimeStore()


# 这个函数根据配置创建运行态；没有显式 Redis URL 时仍会使用默认 Redis。
def get_workflow_runtime_store(force_memory: bool = False) -> WorkflowRuntimeStore:
    config = load_config()
    if force_memory or not config.redis_url:
        return _MEMORY_RUNTIME
    try:
        return RedisWorkflowRuntimeStore(config)
    except Exception:
        return _MEMORY_RUNTIME
