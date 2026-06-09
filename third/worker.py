"""third workflow Redis Stream worker。"""

from __future__ import annotations

import argparse
import time

try:
    from .runtime.factory import get_workflow_runtime_store
    from .storage.factory import get_workflow_repository
    from .workflow.executor import WorkflowExecutor
except ImportError:
    from runtime.factory import get_workflow_runtime_store
    from storage.factory import get_workflow_repository
    from workflow.executor import WorkflowExecutor


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
        WorkflowExecutor(repository=repository, runtime_store=runtime_store).run_session(session_id)
        runtime_store.ack(message_id)
        return True
    finally:
        runtime_store.release_lock(session_id)


# 这个函数启动 worker 循环。
def main() -> None:
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
