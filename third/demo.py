"""第三方服务 LangGraph 的命令行演示入口。"""

from __future__ import annotations

import argparse

from .agents.graph import graph


# 这个函数读取命令行自然语言输入，并用 content[0].text 调用第三方服务 LangGraph。
def main() -> None:
    parser = argparse.ArgumentParser(description="运行第三方服务 LangGraph 演示。")
    parser.add_argument("input", help="给 finagent 的自然语言输入。")
    args = parser.parse_args()

    result = graph.invoke({"content": [{"text": args.input}]})
    content = result.get("content") or []
    if content:
        print(content[0].get("text", ""))
    else:
        print(result)


if __name__ == "__main__":
    main()
