"""第三方服务模块的 LangGraph 固定入口。"""

from __future__ import annotations

from typing import Any

from langgraph.graph import END, StateGraph

try:
    from .state import ThirdServiceState
    from ..workflow.executor import invoke_workflow_sync
except ImportError:
    from agents.state import ThirdServiceState
    from workflow.executor import invoke_workflow_sync


# 这个节点调用 workflow runtime，同步执行到完成、失败或等待用户确认。
def workflow_node(state: ThirdServiceState) -> dict[str, Any]:
    return invoke_workflow_sync(state)


# 这一段定义 LangSmith / LangGraph 使用的固定图；动态性来自 workflow_plan.steps。
workflow = StateGraph(ThirdServiceState)
workflow.add_node("workflow_runtime", workflow_node)
workflow.set_entry_point("workflow_runtime")
workflow.add_edge("workflow_runtime", END)


# 这个对象是 LangGraph / LangSmith 读取的编译后图实例。
graph = workflow.compile()
