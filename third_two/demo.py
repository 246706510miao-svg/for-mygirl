"""third_two 命令行演示入口。"""

from __future__ import annotations

import argparse
import json

from .executor import RollingTaskExecutor


def main() -> None:
    parser = argparse.ArgumentParser(description="运行 third_two 滚动策划任务。")
    parser.add_argument("text", help="用户任务文本")
    parser.add_argument("--max-steps", type=int, default=20)
    args = parser.parse_args()

    executor = RollingTaskExecutor()
    state = executor.create_task(args.text, max_steps=args.max_steps)
    state = executor.run_until_boundary(state.task_id)
    print(json.dumps(state.to_dict(), ensure_ascii=False, indent=2, default=str))


if __name__ == "__main__":
    main()
