"""第三方服务模块的 LangGraph 编排。"""

from __future__ import annotations

from typing import Any

from langgraph.graph import END, StateGraph

try:
    from .finagent.agent import (
        CREATE_TOOL_NAME,
        DELETE_TOOL_NAME,
        READ_TOOL_NAME,
        UPDATE_TOOL_NAME,
        get_tool_call_name,
        run_finagent,
    )
    from .state import ThirdServiceState
    from ..Tool.tool_CreateFeishuBitableRecord import run_tool_CreateFeishuBitableRecord
    from ..Tool.tool_DeleteFeishuBitableRecord import run_tool_DeleteFeishuBitableRecord
    from ..Tool.tool_ReadFeishuBitable import run_tool_ReadFeishuBitable
    from ..Tool.tool_UpdateFeishuBitableRecord import run_tool_UpdateFeishuBitableRecord
except ImportError:
    from Tool.tool_CreateFeishuBitableRecord import run_tool_CreateFeishuBitableRecord
    from Tool.tool_DeleteFeishuBitableRecord import run_tool_DeleteFeishuBitableRecord
    from Tool.tool_ReadFeishuBitable import run_tool_ReadFeishuBitable
    from Tool.tool_UpdateFeishuBitableRecord import run_tool_UpdateFeishuBitableRecord
    from agents.finagent.agent import (
        CREATE_TOOL_NAME,
        DELETE_TOOL_NAME,
        READ_TOOL_NAME,
        UPDATE_TOOL_NAME,
        get_tool_call_name,
        run_finagent,
    )
    from agents.state import ThirdServiceState


# 这个节点调用 finagent，由它决定调用工具或生成最终 answer。
def finagent_node(state: ThirdServiceState) -> dict[str, Any]:
    return run_finagent(state)


# 这个节点调用飞书读取工具，工具结果仍以 content[0].text 交还给 finagent。
def tool_read_feishu_bitable_node(state: ThirdServiceState) -> dict[str, Any]:
    return run_tool_ReadFeishuBitable(state)


# 这个节点调用飞书新增工具，工具结果仍以 content[0].text 交还给 finagent。
def tool_create_feishu_bitable_record_node(state: ThirdServiceState) -> dict[str, Any]:
    return run_tool_CreateFeishuBitableRecord(state)


# 这个节点调用飞书更新工具，工具结果仍以 content[0].text 交还给 finagent。
def tool_update_feishu_bitable_record_node(state: ThirdServiceState) -> dict[str, Any]:
    return run_tool_UpdateFeishuBitableRecord(state)


# 这个节点调用飞书删除工具，工具结果仍以 content[0].text 交还给 finagent。
def tool_delete_feishu_bitable_record_node(state: ThirdServiceState) -> dict[str, Any]:
    return run_tool_DeleteFeishuBitableRecord(state)


# 这个函数决定 finagent 之后进入哪个工具节点或结束图。
def choose_next_node(state: ThirdServiceState) -> str:
    return get_tool_call_name(state) or "answer"


# 这一段定义第三方服务主图，只有 finagent 可以作为最终返回节点。
workflow = StateGraph(ThirdServiceState)
workflow.add_node("finagent", finagent_node)
workflow.add_node(READ_TOOL_NAME, tool_read_feishu_bitable_node)
workflow.add_node(CREATE_TOOL_NAME, tool_create_feishu_bitable_record_node)
workflow.add_node(UPDATE_TOOL_NAME, tool_update_feishu_bitable_record_node)
workflow.add_node(DELETE_TOOL_NAME, tool_delete_feishu_bitable_record_node)

workflow.set_entry_point("finagent")
workflow.add_conditional_edges(
    "finagent",
    choose_next_node,
    {
        READ_TOOL_NAME: READ_TOOL_NAME,
        CREATE_TOOL_NAME: CREATE_TOOL_NAME,
        UPDATE_TOOL_NAME: UPDATE_TOOL_NAME,
        DELETE_TOOL_NAME: DELETE_TOOL_NAME,
        "answer": END,
    },
)
workflow.add_edge(READ_TOOL_NAME, "finagent")
workflow.add_edge(CREATE_TOOL_NAME, "finagent")
workflow.add_edge(UPDATE_TOOL_NAME, "finagent")
workflow.add_edge(DELETE_TOOL_NAME, "finagent")

# 这个对象是 LangGraph / LangSmith 读取的编译后图实例。
graph = workflow.compile()
