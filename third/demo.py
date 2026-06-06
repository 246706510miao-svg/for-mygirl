"""第三方服务 LangGraph 的命令行演示入口。"""

from __future__ import annotations

import argparse

from .agents.graph import graph


# 这个函数读取命令行自然语言输入，并调用第三方服务 LangGraph。
def main() -> None:
    parser = argparse.ArgumentParser(description="运行第三方服务 LangGraph 演示。")
    parser.add_argument("input", help="给 Router Agent 的自然语言输入。")
    args = parser.parse_args()

    result = graph.invoke({"input": args.input})
    print(result.get("output", result))


if __name__ == "__main__":
    main()
