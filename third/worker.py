"""third workflow Redis Stream worker。"""

from __future__ import annotations

import argparse
import logging
import time

try:
    from .runtime.factory import get_workflow_runtime_store
    from .storage.factory import get_workflow_repository
    from .workflow.executor import WorkflowExecutor
except ImportError:
    from runtime.factory import get_workflow_runtime_store
    from storage.factory import get_workflow_repository
    from workflow.executor import WorkflowExecutor


# 这个日志器用于 worker 自身的启动和消费状态输出。
LOGGER = logging.getLogger(__name__)


# 这个函数消费并执行一条 workflow 任务。
def process_one(block_ms: int = 1000) -> bool:
    repository = get_workflow_repository()
    runtime_store = get_workflow_runtime_store()
    message = runtime_store.consume_one(block_ms=block_ms)
    if not message:
        return False
    session_id = str(message.get("session_id") or "")
    message_id = str(message.get("message_id") or "")
    if not session_id:
        runtime_store.ack(message_id)
        return False
    delivery_count = int(message.get("delivery_count") or 1)
    max_deliveries = _max_deliveries(runtime_store)
    if delivery_count > max_deliveries:
        reason = f"workflow 消息超过最大投递次数：{delivery_count}>{max_deliveries}"
        LOGGER.error("%s，session=%s message=%s", reason, session_id, message_id)
        _mark_session_failed(repository, session_id, reason)
        runtime_store.dead_letter(message, reason)
        runtime_store.ack(message_id)
        return True
    if not runtime_store.acquire_lock(session_id):
        LOGGER.warning(
            "workflow session 已被其他 worker 锁定，保留 pending 等待回收：session=%s message=%s delivery=%s",
            session_id,
            message_id,
            delivery_count,
        )
        return False
    try:
        LOGGER.info(
            "开始执行 workflow session：%s message=%s source=%s delivery=%s",
            session_id,
            message_id,
            message.get("source") or "unknown",
            delivery_count,
        )
        WorkflowExecutor(repository=repository, runtime_store=runtime_store).run_session(session_id)
        runtime_store.ack(message_id)
        LOGGER.info("完成执行 workflow session：%s", session_id)
        return True
    except Exception:
        LOGGER.exception("workflow session 执行异常，保留 pending 等待回收：%s", session_id)
        return False
    finally:
        runtime_store.release_lock(session_id)


# 这个函数读取最大投递次数，兼容测试里的内存 runtime。
def _max_deliveries(runtime_store: object) -> int:
    config = getattr(runtime_store, "config", None)
    value = getattr(config, "workflow_max_deliveries", 5)
    try:
        return max(1, int(value))
    except Exception:
        return 5


# 这个函数在消息死信时同步标记 workflow session 失败。
def _mark_session_failed(repository: object, session_id: str, reason: str) -> None:
    try:
        repository.update_session(session_id, status="failed", error_text=reason)
    except Exception:
        LOGGER.exception("标记 workflow session failed 失败：%s", session_id)


# 这个函数配置 worker 控制台日志，确保能直接看到 workflow_plan JSON。
def _configure_logging() -> None:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s %(message)s",
    )


# 这个函数启动 worker 循环。
def main() -> None:
    _configure_logging()
    parser = argparse.ArgumentParser(description="运行 third workflow worker。")
    parser.add_argument("--once", action="store_true", help="只消费一条任务后退出。")
    parser.add_argument("--sleep", type=float, default=0.5, help="无任务时的休眠秒数。")
    args = parser.parse_args()

    while True:
        processed = process_one()
        if args.once:
            break
        if not processed:
            time.sleep(args.sleep)


if __name__ == "__main__":
    main()
