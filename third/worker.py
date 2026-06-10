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
    if not runtime_store.acquire_lock(session_id):
        return False
    try:
        LOGGER.info("开始执行 workflow session：%s", session_id)
        WorkflowExecutor(repository=repository, runtime_store=runtime_store).run_session(session_id)
        runtime_store.ack(message_id)
        LOGGER.info("完成执行 workflow session：%s", session_id)
        return True
    finally:
        runtime_store.release_lock(session_id)


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
