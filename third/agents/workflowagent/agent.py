"""workflowagent：把自然语言请求规划成动态 workflow_plan。"""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

try:
    from ..shared.config import ThirdServiceConfig, load_config
    from ...storage.factory import get_workflow_repository
    from ...workflow.content import load_json_object
except ImportError:
    from agents.shared.config import ThirdServiceConfig, load_config
    from storage.factory import get_workflow_repository
    from workflow.content import load_json_object


# 这一段定义 workflow 当前允许调用的工具名称。
READ_SCHEMA_TOOL = "tool_ReadFeishuBitableSchema"
READ_TOOL = "tool_ReadFeishuBitable"
CREATE_TOOL = "tool_CreateFeishuBitableRecord"
UPDATE_TOOL = "tool_UpdateFeishuBitableRecord"
DELETE_TOOL = "tool_DeleteFeishuBitableRecord"
WRITE_TOOLS = {CREATE_TOOL, UPDATE_TOOL, DELETE_TOOL}
ALLOWED_TOOLS = {READ_SCHEMA_TOOL, READ_TOOL, CREATE_TOOL, UPDATE_TOOL, DELETE_TOOL}
PARSE_FEISHU_RECORD_PROMPT = "parse_feishu_record.v1"
SEARCH_FEISHU_RECORD_PROMPT = "search_feishu_record.v1"
TOOL_CATALOG = [
    {
        "tool_name": READ_SCHEMA_TOOL,
        "category": "feishu_bitable_schema",
        "side_effect_level": "read",
        "purpose": "读取当前飞书多维表格字段定义，返回可用字段名、字段类型、选项和表信息。",
        "when_to_use": "所有新增、更新、删除写入类 workflow 的第一步；也可用于需要先了解表结构的场景。",
        "input_contract": {"content": [{"text": "读取当前飞书多维表格字段定义"}]},
        "output_artifact": "feishu.table_schema",
        "output_summary": "table_fields，包含 field_names、fields、字段类型和选项。",
        "requires_confirmation": False,
    },
    {
        "tool_name": READ_TOOL,
        "category": "feishu_bitable_records",
        "side_effect_level": "read",
        "purpose": "查询或读取飞书多维表格已有记录。",
        "when_to_use": "用户明确要求查询、读取、搜索、列出已有飞书记录时使用；更新或删除已有记录时，也用于在 parse_payload 后读取候选记录交给 search_agent 匹配；不能用于把新内容写到飞书。",
        "input_contract": {
            "read_request": {
                "operation": "search_records",
                "field_names": [],
                "filter": {"conjunction": "and", "conditions": []},
                "sort": [],
                "page_size": 20,
            }
        },
        "output_artifact": "feishu.records",
        "output_summary": "records、record_count、summary 和字段校验信息。",
        "requires_confirmation": False,
    },
    {
        "tool_name": CREATE_TOOL,
        "category": "feishu_bitable_write",
        "side_effect_level": "write",
        "purpose": "新增飞书多维表格记录。",
        "when_to_use": "用户要求新增、保存、记录、写到飞书且不是修改或删除已有记录时使用。",
        "input_contract": {
            "from_session": ["validation.write_payload"],
            "payload_shape": {
                "create_request": {
                    "fields": "单条新增字段对象",
                    "records": "可选；批量新增时为数组，每个元素包含 fields",
                }
            },
        },
        "output_artifact": "write_result",
        "output_summary": "新增结果、record_id、summary。",
        "requires_confirmation": True,
    },
    {
        "tool_name": UPDATE_TOOL,
        "category": "feishu_bitable_write",
        "side_effect_level": "write",
        "purpose": "更新飞书多维表格已有记录。",
        "when_to_use": "用户要求修改、更新、改成、调整已有记录时使用；payload 必须有 record_id 或 lookup.filter 供 validation 唯一定位。",
        "input_contract": {"from_session": ["validation.write_payload"]},
        "output_artifact": "write_result",
        "output_summary": "更新结果、record_id、summary。",
        "requires_confirmation": True,
    },
    {
        "tool_name": DELETE_TOOL,
        "category": "feishu_bitable_write",
        "side_effect_level": "delete",
        "purpose": "删除飞书多维表格已有记录。",
        "when_to_use": "用户明确要求删除、移除、清理已有记录时使用；payload 必须有 record_id 或 lookup.filter 供 validation 唯一定位。",
        "input_contract": {"from_session": ["validation.write_payload"]},
        "output_artifact": "write_result",
        "output_summary": "删除结果、record_id、summary。",
        "requires_confirmation": True,
    },
]


# 这一段定义规则兜底意图关键词。
READ_KEYWORDS = ("查询", "读取", "搜索", "查找", "查", "列出", "获取", "看看", "看一下", "显示", "总结")
CREATE_KEYWORDS = ("新增", "添加", "创建", "写入", "写到", "写进", "保存", "存到", "同步到", "记录一下", "记一下", "记录到", "记到", "填到")
UPDATE_KEYWORDS = ("修改", "更新", "改成", "改为", "调整")
DELETE_KEYWORDS = ("删除", "移除", "清理")


# 这个函数是 workflowagent 的入口；LLM 模式严格依赖数据库 Agent 目录。
def build_workflow_plan(
    input_text: str,
    config: ThirdServiceConfig | None = None,
    repository: Any | None = None,
    agent_prompts: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    resolved_config = config or load_config()
    if resolved_config.workflowagent_use_llm:
        if not resolved_config.openai_api_key:
            raise RuntimeError("THIRD_WORKFLOWAGENT_USE_LLM=1 但 OPENAI_API_KEY 未配置。")
        available_agents = agent_prompts if agent_prompts is not None else _load_agent_prompts(repository)
        if not available_agents:
            raise RuntimeError("THIRD_WORKFLOWAGENT_USE_LLM=1 但 prompt_registry 中没有启用的 runagent 提示词。")
        return _try_llm_plan(input_text, resolved_config, available_agents)
    return _rule_based_plan(input_text)


# 这个函数尝试调用 OpenAI 生成 workflow_plan。
def _try_llm_plan(input_text: str, config: ThirdServiceConfig, agent_prompts: list[dict[str, Any]]) -> dict[str, Any]:
    try:
        from langchain_openai import ChatOpenAI
    except ImportError as exc:
        raise RuntimeError("缺少 langchain_openai 依赖，无法调用 workflowagent LLM。") from exc

    prompt = f"{_load_prompt(agent_prompts)}\n\n用户 content[0].text：\n{input_text}"
    try:
        response = ChatOpenAI(model=config.workflowagent_model, temperature=0, api_key=config.openai_api_key).invoke(prompt)
    except Exception as exc:
        raise RuntimeError(f"workflowagent LLM 调用失败：{exc}") from exc
    payload = load_json_object(str(getattr(response, "content", "")))
    if isinstance(payload, dict) and payload.get("type") == "workflow_plan":
        return payload
    raise ValueError("workflowagent LLM 输出不是合法 workflow_plan JSON。")


# 这个函数读取 Prompt/workflowagent.yaml 中的系统提示词。
def _load_prompt(agent_prompts: list[dict[str, Any]] | None = None) -> str:
    prompt_path = Path(__file__).resolve().parents[2] / "Prompt" / "workflowagent.yaml"
    if not prompt_path.exists():
        base_prompt = "你是 workflowagent，只输出 workflow_plan JSON。"
        return _append_agent_catalog(base_prompt, agent_prompts or [])
    raw_text = prompt_path.read_text(encoding="utf-8")
    try:
        import yaml

        parsed = yaml.safe_load(raw_text)
        if isinstance(parsed, dict) and parsed.get("system"):
            return _append_agent_catalog(str(parsed["system"]), agent_prompts or [])
    except Exception:
        pass
    return _append_agent_catalog(raw_text, agent_prompts or [])


# 这个函数读取数据库中启用的 Agent 能力目录。
def _load_agent_prompts(repository: Any | None = None) -> list[dict[str, Any]]:
    resolved_repository = repository or get_workflow_repository()
    if not hasattr(resolved_repository, "list_agent_prompts"):
        return []
    return resolved_repository.list_agent_prompts(enabled_only=True)


# 这个函数把数据库 Agent 目录注入 workflowagent 系统提示词。
def _append_agent_catalog(base_prompt: str, agent_prompts: list[dict[str, Any]]) -> str:
    catalog = [
        {
            "agent_name": prompt.get("agent_name"),
            "prompt_ref": prompt.get("prompt_key"),
            "prompt_key": prompt.get("prompt_key"),
            "role_name": prompt.get("role_name"),
            "description": prompt.get("description"),
            "db_address": prompt.get("db_address"),
            "input_schema_json": prompt.get("input_schema_json") or {},
            "output_schema_json": prompt.get("output_schema_json") or {},
            "metadata_json": prompt.get("metadata_json") or {},
            "version": prompt.get("version"),
            "enabled": prompt.get("enabled", True),
        }
        for prompt in agent_prompts
    ]
    return (
        f"{base_prompt}\n\n"
        "# 可用 Tool 能力目录\n"
        "你只能从下面 JSON 中选择 tool_name；必须按 purpose、when_to_use、side_effect_level 和 requires_confirmation 判断是否可用。\n"
        f"{json.dumps(TOOL_CATALOG, ensure_ascii=False, default=str)}\n\n"
        "# 可用业务 Agent 目录\n"
        "你只能从下面 JSON 中选择 agent_name 和 prompt_ref；不得编造未列出的 Agent 或 prompt_ref。"
        "目录中的 role_name、description、input_schema_json、output_schema_json、metadata_json、version、db_address 都是数据库 prompt_registry 的运行时记录；"
        "workflowagent 只负责引用 prompt_ref，Agent Runner 会在执行时按 db_address 从数据库读取 prompt_text。\n"
        f"{json.dumps(catalog, ensure_ascii=False, default=str)}"
    )


# 这个函数在没有 LLM 时生成稳定的规则 workflow_plan。
def _rule_based_plan(input_text: str) -> dict[str, Any]:
    intent = _detect_intent(input_text)
    if intent == "delete_feishu_record":
        return _write_plan(input_text, intent, "delete", DELETE_TOOL, "feishu.delete_payload")
    if intent == "update_feishu_record":
        return _write_plan(input_text, intent, "write", UPDATE_TOOL, "feishu.update_payload")
    if intent == "create_feishu_record":
        return _write_plan(input_text, intent, "write", CREATE_TOOL, "feishu.create_payload")
    return _read_plan(input_text)


# 这个函数根据关键词识别用户目标。
def _detect_intent(input_text: str) -> str:
    if any(keyword in input_text for keyword in DELETE_KEYWORDS):
        return "delete_feishu_record"
    if any(keyword in input_text for keyword in UPDATE_KEYWORDS):
        return "update_feishu_record"
    if any(keyword in input_text for keyword in CREATE_KEYWORDS):
        return "create_feishu_record"
    if any(keyword in input_text for keyword in READ_KEYWORDS):
        return "read_feishu_records"
    if "飞书" in input_text or "多维表格" in input_text or "表格" in input_text:
        return "read_feishu_records"
    return "read_feishu_records"


# 这个函数生成读取类 workflow_plan。
def _read_plan(input_text: str) -> dict[str, Any]:
    read_input = json.dumps(
        {
            "original_input": input_text,
            "read_request": {
                "operation": "search_records",
                "service": "feishu_bitable",
                "field_names": _extract_read_field_names(input_text),
                "filter": {"conjunction": "and", "conditions": _extract_read_conditions(input_text)},
                "sort": [],
                "page_size": 20,
                "automatic_fields": True,
            },
        },
        ensure_ascii=False,
    )
    return {
        "type": "workflow_plan",
        "version": "workflow.v1",
        "intent": "read_feishu_records",
        "risk_level": "read",
        "requires_confirmation": False,
        "original_input": input_text,
        "steps": [
            {
                "step_id": "step_read_records",
                "kind": "tool",
                "tool_name": READ_TOOL,
                "purpose": "读取飞书多维表格记录",
                "input": {"content": [{"text": read_input}]},
                "output": {"save_as": "feishu.records", "content_path": "content[0].text"},
                "validation": {"required": True},
            }
        ],
        "final": {"source": "feishu.records", "format": "answer"},
    }


# 这个函数从读取请求中抽取用户明确要求返回的字段。
def _extract_read_field_names(input_text: str) -> list[str]:
    match = re.search(r"(?:返回|输出|只看|只返回|字段)\s*[:：]?\s*([^，。；;]+(?:[、,，]\s*[^，。；;]+)*)", input_text)
    if not match:
        return []
    fields = [part.strip(" \t\r\n。；;") for part in re.split(r"[、,，\s]+", match.group(1)) if part.strip()]
    return _dedupe(fields)


# 这个函数从读取请求中抽取常见过滤条件，避免 strict 模式下丢失查询语义。
def _extract_read_conditions(input_text: str) -> list[dict[str, Any]]:
    conditions: list[dict[str, Any]] = []
    status_match = re.search(r"状态(?:为|是|=|：|:)?\s*([^\s，。；;]+)", input_text)
    if status_match:
        conditions.append({"field_name": "状态", "operator": "is", "value": _clean_condition_value(status_match.group(1))})
    else:
        for status in ("进行中", "已完成", "待开始", "未完成"):
            if status in input_text:
                conditions.append({"field_name": "状态", "operator": "is", "value": status})
                break

    priority_match = re.search(r"优先级(?:为|是|=|：|:)?\s*([高中低])", input_text)
    if priority_match:
        conditions.append({"field_name": "优先级", "operator": "is", "value": priority_match.group(1)})
    return conditions


# 这个函数清理过滤条件里常见的自然语言后缀。
def _clean_condition_value(value: str) -> str:
    cleaned = value.strip()
    for known in ("进行中", "已完成", "待开始", "未完成"):
        if known in cleaned:
            return known
    return re.sub(r"(的)?记录$", "", cleaned)


# 这个函数在保留顺序的同时去重。
def _dedupe(items: list[str]) -> list[str]:
    seen: set[str] = set()
    result: list[str] = []
    for item in items:
        if item not in seen:
            seen.add(item)
            result.append(item)
    return result


# 这个函数生成新增、更新、删除类 workflow_plan。
def _write_plan(input_text: str, intent: str, risk_level: str, write_tool: str, payload_key: str) -> dict[str, Any]:
    plan = {
        "type": "workflow_plan",
        "version": "workflow.v1",
        "intent": intent,
        "risk_level": risk_level,
        "requires_confirmation": True,
        "original_input": input_text,
        "final": {"source": "write_result", "format": "answer"},
        "steps": [
            {
                "step_id": "step_read_schema",
                "kind": "tool",
                "tool_name": READ_SCHEMA_TOOL,
                "purpose": "读取飞书字段定义",
                "input": {"content": [{"text": "读取当前飞书多维表格字段定义"}]},
                "output": {"save_as": "feishu.table_schema", "content_path": "content[0].text"},
                "validation": {"required": True},
            },
            {
                "step_id": "step_parse_payload",
                "kind": "agent",
                "agent_name": "business_agent",
                "prompt_ref": PARSE_FEISHU_RECORD_PROMPT,
                "purpose": "把用户输入转换为飞书写入 payload",
                "input": {"from_session": ["feishu.table_schema"], "include_original_input": True},
                "output": {"save_as": payload_key},
                "validation": {"reject_unknown_fields": True, "must_match_feishu_schema": True},
            },
        ]
    }
    if write_tool in {UPDATE_TOOL, DELETE_TOOL}:
        plan["steps"].extend(
            [
                {
                    "step_id": "step_read_candidate_records",
                    "kind": "tool",
                    "tool_name": READ_TOOL,
                    "purpose": "读取候选飞书记录供 search_agent 匹配",
                    "input": {
                        "from_session": [payload_key],
                        "tool_payload_from": {"artifact_key": payload_key, "path": "data_json.candidate_read_payload"},
                    },
                    "output": {"save_as": "feishu.candidate_records", "content_path": "content[0].text"},
                    "validation": {"required": True},
                },
                {
                    "step_id": "step_match_record",
                    "kind": "agent",
                    "agent_name": "search_agent",
                    "prompt_ref": SEARCH_FEISHU_RECORD_PROMPT,
                    "purpose": "根据用户输入和候选记录匹配待更新或删除的 record_id",
                    "input": {"from_session": [payload_key, "feishu.candidate_records"], "include_original_input": True},
                    "output": {"save_as": "feishu.record_match"},
                    "validation": {"must_select_candidate_record": True},
                },
            ]
        )
        validation_inputs = ["feishu.table_schema", payload_key, "feishu.record_match"]
    else:
        validation_inputs = ["feishu.table_schema", payload_key]

    plan["steps"].extend(
        [
            {
                "step_id": "step_validate_payload",
                "kind": "validation",
                "purpose": "校验写入 payload 字段、匹配记录和定位条件",
                "input": {"from_session": validation_inputs},
                "output": {"save_as": "validation.write_payload"},
                "validation": {"operation_intent": intent, "write_tool": write_tool},
            },
            {
                "step_id": "step_confirm_write",
                "kind": "confirm",
                "purpose": "等待用户确认写入操作",
                "input": {"from_session": ["validation.write_payload"]},
                "output": {"save_as": "confirmation.write"},
                "validation": {"required": True},
            },
            {
                "step_id": "step_write_feishu",
                "kind": "tool",
                "tool_name": write_tool,
                "purpose": "执行飞书写入类操作",
                "input": {"from_session": ["validation.write_payload"]},
                "output": {"save_as": "write_result", "content_path": "content[0].text"},
                "validation": {"idempotent": True},
            },
        ]
    )
    return plan
