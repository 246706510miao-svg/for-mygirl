"""第三方服务模块的 LangGraph 编排。"""

from __future__ import annotations

from typing import Any

from langgraph.graph import END, StateGraph

try:
    from .read.field_context import load_table_fields_context
    from .read.agent import run_read_agent
    from .router.agent import route_user_input
    from .state import ThirdServiceState
except ImportError:
    from agents.read.field_context import load_table_fields_context
    from agents.read.agent import run_read_agent
    from agents.router.agent import route_user_input
    from agents.state import ThirdServiceState


# 这个节点在 Router Agent 之前读取当前飞书表字段，给路由提供真实字段上下文。
def load_table_fields_node(state: ThirdServiceState) -> dict[str, Any]:
    return {
        "input": _extract_input(state),
        "table_fields": load_table_fields_context(),
    }


# 这个节点调用 Router Agent，把用户自然语言整理成结构化路由结果。
def router_node(state: ThirdServiceState) -> dict[str, Any]:
    user_input = _extract_input(state)
    route = route_user_input(user_input, table_fields=state.get("table_fields"))
    update: dict[str, Any] = {
        "input": user_input,
        "route": route,
    }
    if route.get("read_request"):
        update["read_request"] = route["read_request"]
    return update


# 这个节点调用 Read Agent，读取真实或 mock 飞书多维表格记录。
def read_node(state: ThirdServiceState) -> dict[str, Any]:
    read_request = dict(state.get("read_request", {}))
    if state.get("table_fields"):
        read_request["table_fields"] = state["table_fields"]
    return run_read_agent(read_request, original_input=state.get("input", ""))


# 这个节点处理尚未实现的写入、修改、删除和澄清意图。
def unsupported_node(state: ThirdServiceState) -> dict[str, Any]:
    route = state.get("route", {})
    intent = route.get("intent", "clarify")
    reason = route.get("reason", "当前输入无法进入读取流程。")
    output = f"当前只实现 Router Agent 与 Read Agent，无法执行 `{intent}` 意图。{reason}"
    return {"output": output}


# 这个函数决定 Router Agent 之后进入 Read Agent 还是未支持意图处理节点。
def choose_next_node(state: ThirdServiceState) -> str:
    route = state.get("route", {})
    if route.get("intent") == "read":
        return "read_agent"
    return "unsupported"


# 这个函数从 LangGraph 状态中取出用户输入。
def _extract_input(state: ThirdServiceState) -> str:
    if state.get("input"):
        return str(state["input"])
    return ""


# 这一段定义第三方服务主图，先读取字段上下文，再串联 Router Agent 和 Read Agent。
workflow = StateGraph(ThirdServiceState)
workflow.add_node("load_table_fields", load_table_fields_node)
workflow.add_node("router_agent", router_node)
workflow.add_node("read_agent", read_node)
workflow.add_node("unsupported", unsupported_node)

workflow.set_entry_point("load_table_fields")
workflow.add_edge("load_table_fields", "router_agent")
workflow.add_conditional_edges(
    "router_agent",
    choose_next_node,
    {
        "read_agent": "read_agent",
        "unsupported": "unsupported",
    },
)
workflow.add_edge("read_agent", END)
workflow.add_edge("unsupported", END)

# 这个对象是 LangGraph / LangSmith 读取的编译后图实例。
graph = workflow.compile()
