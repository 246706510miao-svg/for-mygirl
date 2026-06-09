"""第三方服务 workflow 的命令行演示入口。"""

from __future__ import annotations

import argparse
import json

from .agents.graph import graph
from .api import get_workflow, invoke_workflow, resume_workflow
from .worker import process_one
from .workflow.api_schema import ContentPart, InvokeWorkflowRequest, ResumeWorkflowRequest


# 这个函数读取命令行参数，并演示同步 LangGraph 或异步 API/worker 流程。
def main() -> None:
    parser = argparse.ArgumentParser(description="运行第三方服务 workflow 演示。")
    parser.add_argument("input", nargs="?", help="给 workflowagent 的自然语言输入。")
    parser.add_argument("--submit", action="store_true", help="只提交异步 workflow，不同步执行。")
    parser.add_argument("--worker-once", action="store_true", help="消费并执行一条异步 workflow 任务。")
    parser.add_argument("--status", help="查询指定 session_id 的 workflow 状态。")
    parser.add_argument("--resume", help="恢复指定 session_id。")
    parser.add_argument("--confirmation-id", help="resume 时传入的 confirmation_id。")
    parser.add_argument("--approve", action="store_true", help="resume 时确认继续执行。")
    parser.add_argument("--reject", action="store_true", help="resume 时拒绝继续执行。")
    args = parser.parse_args()

    if args.worker_once:
        print(json.dumps({"processed": process_one(block_ms=10)}, ensure_ascii=False))
        return
    if args.status:
        print(get_workflow(args.status).model_dump_json())
        return
    if args.resume:
        if not args.confirmation_id:
            raise SystemExit("--resume 需要同时提供 --confirmation-id。")
        approved = args.approve and not args.reject
        response = resume_workflow(
            args.resume,
            ResumeWorkflowRequest(
                confirmation_id=args.confirmation_id,
                approved=approved,
                content=[ContentPart(text=args.input or "")],
            ),
        )
        print(response.model_dump_json())
        return
    if args.submit:
        if not args.input:
            raise SystemExit("--submit 需要提供自然语言 input。")
        response = invoke_workflow(InvokeWorkflowRequest(content=[ContentPart(text=args.input)]))
        print(response.model_dump_json())
        return
    if not args.input:
        raise SystemExit("请提供自然语言 input，或使用 --worker-once / --status / --resume。")

    result = graph.invoke({"content": [{"text": args.input}]})
    content = result.get("content") or []
    if content:
        print(content[0].get("text", ""))
    else:
        print(result)


if __name__ == "__main__":
    main()
