"""finagent：第三方服务模块唯一的决策 Agent。"""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any, Literal

try:
    from ..shared.config import ThirdServiceConfig, load_config
except ImportError:
    from agents.shared.config import ThirdServiceConfig, load_config


# 这一段定义 finagent 可以调用的工具名称，后续新增工具时统一扩展这里。
READ_TOOL_NAME = "tool_ReadFeishuBitable"
CREATE_TOOL_NAME = "tool_CreateFeishuBitableRecord"
UPDATE_TOOL_NAME = "tool_UpdateFeishuBitableRecord"
DELETE_TOOL_NAME = "tool_DeleteFeishuBitableRecord"
ALLOWED_TOOL_NAMES = {READ_TOOL_NAME, CREATE_TOOL_NAME, UPDATE_TOOL_NAME, DELETE_TOOL_NAME}
TOOL_NAME_BY_INTENT = {
    "read": READ_TOOL_NAME,
    "write": CREATE_TOOL_NAME,
    "update": UPDATE_TOOL_NAME,
    "delete": DELETE_TOOL_NAME,
}


# 这一段定义 finagent 的轻量规则关键词，LLM 不可用时仍能稳定决策。
READ_KEYWORDS = ("查询", "读取", "搜索", "查找", "查", "找", "列出", "获取", "看看", "看一下", "显示")
READ_CONTEXT_KEYWORDS = ("飞书", "多维表格", "表格", "记录", "数据", "内容")
READ_QUESTION_KEYWORDS = ("有什么", "有哪些", "是什么", "现在有什么", "里面有什么", "总结", "统计")
WRITE_KEYWORDS = ("新增", "添加", "创建", "写入", "记录一下", "保存")
UPDATE_KEYWORDS = ("修改", "更新", "改成", "调整")
DELETE_KEYWORDS = ("删除", "移除", "清理")
IRRELEVANT_KEYWORDS = ("天气", "笑话", "翻译", "闲聊")


# 这一段定义 finagent 的动作类型，tool_call 会进入工具节点，answer 会结束图。
AgentAction = Literal["tool_call", "answer"]


# 这个函数是 finagent 的 LangGraph 节点入口，输入和输出都只通过 content[0].text 传递。
def run_finagent(state: dict[str, Any]) -> dict[str, Any]:
    config = load_config()
    input_text = _extract_content_text(state)
    if not input_text:
        return _content(_strict_error("输入为空，请通过 content[0].text 提供请求。") if config.finagent_use_llm else "请提供需要查询的内容。")

    tool_result = _load_tool_result(input_text)
    if tool_result:
        return _content(_summarize_tool_result(tool_result, config))

    if config.finagent_use_llm:
        return _content(_run_strict_llm_decision(input_text, config))

    llm_decision = _try_llm_decision(input_text, config)
    if llm_decision:
        return _content(_normalize_llm_decision(llm_decision, input_text))

    return _content(_rule_based_decision(input_text))


# 这个函数判断 finagent 当前输出是否是指定工具调用，供 LangGraph 条件边使用。
def is_tool_call_for(state: dict[str, Any], tool_name: str) -> bool:
    payload = _load_json_object(_extract_content_text(state))
    return bool(
        isinstance(payload, dict)
        and payload.get("type") == "tool_call"
        and payload.get("tool_name") == tool_name
    )


# 这个函数读取当前 finagent 输出的 tool_name，供 LangGraph 多工具路由使用。
def get_tool_call_name(state: dict[str, Any]) -> str | None:
    payload = _load_json_object(_extract_content_text(state))
    if not isinstance(payload, dict) or payload.get("type") != "tool_call":
        return None
    tool_name = str(payload.get("tool_name") or "")
    return tool_name if tool_name in ALLOWED_TOOL_NAMES else None


# 这个函数从标准 content 数组里提取 text，兼容外部误传 input 的调试场景。
def _extract_content_text(state: dict[str, Any]) -> str:
    content = state.get("content") or []
    if content and isinstance(content, list):
        first = content[0] or {}
        if isinstance(first, dict):
            return str(first.get("text") or "").strip()
    return str(state.get("input") or "").strip()


# 这个函数把文本包装成统一的 content[0].text 结构。
def _content(text: str) -> dict[str, list[dict[str, str]]]:
    return {"content": [{"text": text}]}


# 这个函数识别 tool_ReadFeishuBitable 返回的 tool_result JSON。
def _load_tool_result(text: str) -> dict[str, Any] | None:
    payload = _load_json_object(text)
    if not isinstance(payload, dict):
        return None
    if payload.get("type") != "tool_result":
        return None
    if payload.get("tool_name") not in ALLOWED_TOOL_NAMES:
        return None
    return payload


# 这个函数在没有 LLM 或模型不可用时，按规则决定调用工具还是直接回答。
def _rule_based_decision(input_text: str) -> str:
    intent = _detect_intent(input_text)
    if intent in TOOL_NAME_BY_INTENT:
        return _tool_call_text(TOOL_NAME_BY_INTENT[intent], input_text)
    if intent == "irrelevant":
        return "当前模块只处理飞书多维表格记录的读取、新增、更新和删除。"
    return "请补充要操作的飞书多维表格内容，例如要查询、新增、修改或删除哪条记录。"


# 这个函数根据关键词判断用户意图，当前只有 read 会触发工具。
def _detect_intent(input_text: str) -> str:
    lower_input = input_text.lower()
    if any(keyword in input_text for keyword in IRRELEVANT_KEYWORDS):
        return "irrelevant"
    if any(keyword in input_text for keyword in DELETE_KEYWORDS):
        return "delete"
    if any(keyword in input_text for keyword in UPDATE_KEYWORDS):
        return "update"
    if any(keyword in input_text for keyword in WRITE_KEYWORDS):
        return "write"
    if any(keyword in input_text for keyword in READ_KEYWORDS):
        return "read"
    if _looks_like_feishu_read_question(input_text):
        return "read"
    if any(token in lower_input for token in ("read", "search", "list", "get")):
        return "read"
    return "clarify"


# 这个函数识别“我的飞书里现在有什么内容”这类没有显式查询动词的读取问题。
def _looks_like_feishu_read_question(input_text: str) -> bool:
    has_context = any(keyword in input_text for keyword in READ_CONTEXT_KEYWORDS)
    has_question = any(keyword in input_text for keyword in READ_QUESTION_KEYWORDS)
    if has_context and has_question:
        return True
    if "飞书" in input_text and any(keyword in input_text for keyword in ("内容", "记录", "数据")):
        return True
    return False


# 这个函数把工具调用包装成 content[0].text 内的 JSON 字符串。
def _tool_call_text(tool_name: str, tool_input_text: str) -> str:
    return json.dumps(
        {
            "type": "tool_call",
            "tool_name": tool_name,
            "content": [{"text": tool_input_text}],
        },
        ensure_ascii=False,
    )


# 这个函数把 LLM 输出归一化成图可以理解的 content[0].text。
def _normalize_llm_decision(decision: dict[str, Any], fallback_input: str) -> str:
    decision_type = decision.get("type")
    tool_name = str(decision.get("tool_name") or "")
    if decision_type == "tool_call" and tool_name in ALLOWED_TOOL_NAMES:
        tool_text = _extract_content_text(decision) or fallback_input
        return _tool_call_text(tool_name, tool_text)

    if decision_type == "answer":
        answer_text = _extract_content_text(decision)
        if answer_text:
            return answer_text

    return _rule_based_decision(fallback_input)


# 这个函数在 strict LLM 模式下执行决策，任何失败都返回错误而不是规则兜底。
def _run_strict_llm_decision(input_text: str, config: ThirdServiceConfig) -> str:
    if not config.openai_api_key:
        return _strict_error("THIRD_FINAGENT_USE_LLM=1 但 OPENAI_API_KEY 未配置。")
    try:
        response_text = _invoke_finagent_model(_build_decision_prompt(input_text), config)
    except ImportError:
        return _strict_error("缺少 langchain_openai 依赖，无法调用 LLM。")
    except Exception as exc:
        return _strict_error(f"LLM 决策调用失败：{exc}")

    decision = _load_json_object(response_text)
    if not isinstance(decision, dict):
        return _strict_error("LLM 决策输出不是合法 JSON 对象。")
    return _normalize_strict_llm_decision(decision)


# 这个函数校验 strict LLM 模式下的决策 JSON，不允许回退到规则。
def _normalize_strict_llm_decision(decision: dict[str, Any]) -> str:
    decision_type = decision.get("type")
    if decision_type == "tool_call":
        tool_name = str(decision.get("tool_name") or "")
        if tool_name not in ALLOWED_TOOL_NAMES:
            return _strict_error("LLM 决策输出了不允许的 tool_name。")
        tool_text = _extract_content_text(decision)
        if not tool_text:
            return _strict_error("LLM 的 tool_call 缺少 content[0].text。")
        return _tool_call_text(tool_name, tool_text)

    if decision_type == "answer":
        answer_text = _extract_content_text(decision)
        if not answer_text:
            return _strict_error("LLM 的 answer 缺少 content[0].text。")
        return answer_text

    return _strict_error("LLM 决策输出的 type 不是 tool_call 或 answer。")


# 这个函数在启用 LLM 时读取 Prompt/finagent.yaml，并让模型输出下一步动作。
def _try_llm_decision(input_text: str, config: ThirdServiceConfig) -> dict[str, Any] | None:
    if not config.finagent_use_llm:
        return None
    if not config.openai_api_key:
        return None
    try:
        from langchain_openai import ChatOpenAI
    except ImportError:
        return None

    try:
        content = _invoke_finagent_model(_build_decision_prompt(input_text), config)
    except Exception:
        return None
    return _load_json_object(content)


# 这个函数组合 finagent 的系统提示词和当前输入。
def _build_decision_prompt(input_text: str) -> str:
    prompt_config = _load_finagent_prompt()
    system_prompt = prompt_config.get("system") or _default_system_prompt()
    return f"{system_prompt}\n\n当前 content[0].text：\n{input_text}"


# 这个函数读取 Prompt/finagent.yaml，避免提示词散落在 Agent 代码里。
def _load_finagent_prompt() -> dict[str, str]:
    prompt_path = Path(__file__).resolve().parents[2] / "Prompt" / "finagent.yaml"
    if not prompt_path.exists():
        return {"system": _default_system_prompt()}

    raw_prompt = prompt_path.read_text(encoding="utf-8")
    try:
        import yaml

        parsed = yaml.safe_load(raw_prompt)
        if isinstance(parsed, dict):
            return {str(key): str(value) for key, value in parsed.items() if value is not None}
    except Exception:
        pass

    return {"system": _extract_yaml_block(raw_prompt, "system") or _default_system_prompt()}


# 这个函数在没有 PyYAML 时读取简单的 YAML 块内容。
def _extract_yaml_block(raw_prompt: str, key: str) -> str:
    lines = raw_prompt.splitlines()
    for index, line in enumerate(lines):
        if line.strip() != f"{key}: |":
            continue
        block_lines: list[str] = []
        for block_line in lines[index + 1 :]:
            if block_line and not block_line.startswith(" "):
                break
            block_lines.append(block_line[2:] if block_line.startswith("  ") else block_line)
        return "\n".join(block_lines).strip()
    return ""


# 这个函数提供提示词文件缺失时的最小兜底提示词。
def _default_system_prompt() -> str:
    return (
        "你是第三方服务模块的 finagent。"
        "需要操作飞书多维表格时输出允许工具的 tool_call JSON；"
        "拿到 tool_result 或无需工具时输出 answer JSON。"
    )


# 这个函数把工具读取结果整理成最终中文答案，只有 finagent 会执行这一步。
def _summarize_tool_result(tool_result: dict[str, Any], config: ThirdServiceConfig) -> str:
    if config.finagent_use_llm:
        return _run_strict_llm_answer(tool_result, config)

    llm_answer = _try_llm_answer(tool_result, config)
    if llm_answer:
        return llm_answer
    return _rule_based_tool_summary(tool_result)


# 这个函数在 strict LLM 模式下总结工具结果，失败时只返回错误。
def _run_strict_llm_answer(tool_result: dict[str, Any], config: ThirdServiceConfig) -> str:
    if not config.openai_api_key:
        return _strict_error("THIRD_FINAGENT_USE_LLM=1 但 OPENAI_API_KEY 未配置，无法总结 tool_result。")

    prompt_config = _load_finagent_prompt()
    system_prompt = prompt_config.get("system") or _default_system_prompt()
    prompt = (
        f"{system_prompt}\n\n"
        "下面是 tool_ReadFeishuBitable 的 tool_result。"
        "请输出 answer JSON，content[0].text 是给用户的最终中文答案。\n"
        f"{json.dumps(tool_result, ensure_ascii=False)}"
    )
    try:
        response_text = _invoke_finagent_model(prompt, config)
    except ImportError:
        return _strict_error("缺少 langchain_openai 依赖，无法总结 tool_result。")
    except Exception as exc:
        return _strict_error(f"LLM 总结 tool_result 失败：{exc}")

    decision = _load_json_object(response_text)
    if not isinstance(decision, dict):
        return _strict_error("LLM 总结输出不是合法 JSON 对象。")
    if decision.get("type") != "answer":
        return _strict_error("LLM 总结输出的 type 不是 answer。")
    answer_text = _extract_content_text(decision)
    if not answer_text:
        return _strict_error("LLM 总结 answer 缺少 content[0].text。")
    return answer_text


# 这个函数在启用 LLM 时让 finagent 基于 tool_result 生成最终答案。
def _try_llm_answer(tool_result: dict[str, Any], config: ThirdServiceConfig) -> str | None:
    if not config.finagent_use_llm or not config.openai_api_key:
        return None
    try:
        from langchain_openai import ChatOpenAI
    except ImportError:
        return None

    prompt_config = _load_finagent_prompt()
    system_prompt = prompt_config.get("system") or _default_system_prompt()
    prompt = (
        f"{system_prompt}\n\n"
        "下面是 tool_ReadFeishuBitable 的 tool_result。"
        "请输出 answer JSON，content[0].text 是给用户的最终中文答案。\n"
        f"{json.dumps(tool_result, ensure_ascii=False)}"
    )
    model = ChatOpenAI(model=config.finagent_model, temperature=0, api_key=config.openai_api_key)
    response = model.invoke(prompt)
    decision = _load_json_object(str(getattr(response, "content", "")))
    if isinstance(decision, dict) and decision.get("type") == "answer":
        return _extract_content_text(decision) or None
    return str(getattr(response, "content", "")).strip() or None


# 这个函数统一调用 finagent 使用的 OpenAI 模型，便于 strict 和非 strict 路径复用。
def _invoke_finagent_model(prompt: str, config: ThirdServiceConfig) -> str:
    from langchain_openai import ChatOpenAI

    model = ChatOpenAI(model=config.finagent_model, temperature=0, api_key=config.openai_api_key)
    response = model.invoke(prompt)
    return str(getattr(response, "content", "")).strip()


# 这个函数生成 strict 模式下的明确错误文本，避免误判成 tool_call。
def _strict_error(message: str) -> str:
    return f"LLM strict mode 错误：{message}"


# 这个函数在无 LLM 时把 tool_result 转换成稳定可读的最终答案。
def _rule_based_tool_summary(tool_result: dict[str, Any]) -> str:
    if tool_result.get("error"):
        lines = [f"操作失败：{tool_result['error']}"]
        warnings = tool_result.get("warnings") or []
        if warnings:
            lines.append(f"提示：{'；'.join(str(warning) for warning in warnings)}")
        return "\n".join(lines)

    operation = str(tool_result.get("operation") or "")
    if operation in {"create_record", "update_record", "delete_record"}:
        return _rule_based_write_summary(tool_result)

    records = tool_result.get("records") or []
    record_count = int(tool_result.get("record_count") or len(records))
    source = "真实飞书多维表格" if tool_result.get("backend") == "feishu" else "mock 飞书表"
    if not records:
        return f"未查询到匹配记录。数据来源：{source}。"

    lines = [f"查询到 {record_count} 条记录，数据来源：{source}。"]
    for index, record in enumerate(records[:10], start=1):
        fields = record.get("fields") or {}
        field_text = _format_record_fields(fields)
        if field_text:
            lines.append(f"{index}. {field_text}")
        else:
            lines.append(f"{index}. record_id：{record.get('record_id', '')}")
    if record_count > 10:
        lines.append(f"还有 {record_count - 10} 条记录未在当前答案中展开。")
    return "\n".join(lines)


# 这个函数在无 LLM 时把写入类 tool_result 转换成稳定可读的最终答案。
def _rule_based_write_summary(tool_result: dict[str, Any]) -> str:
    operation = str(tool_result.get("operation") or "")
    operation_label = {
        "create_record": "新增",
        "update_record": "更新",
        "delete_record": "删除",
    }.get(operation, "操作")
    source = "真实飞书多维表格" if tool_result.get("backend") == "feishu" else "mock 飞书表"
    record = tool_result.get("record") or {}
    record_id = record.get("record_id") or tool_result.get("request", {}).get("record_id") or ""
    fields = record.get("fields") or {}

    lines = [f"{operation_label}成功。数据来源：{source}。"]
    if record_id:
        lines.append(f"record_id：{record_id}")
    if fields:
        lines.append(f"字段：{_format_record_fields(fields)}")
    warnings = tool_result.get("warnings") or []
    if warnings:
        lines.append(f"提示：{'；'.join(str(warning) for warning in warnings)}")
    return "\n".join(lines)


# 这个函数把单条记录的字段映射压缩成一行中文文本。
def _format_record_fields(fields: dict[str, Any]) -> str:
    parts = []
    for field_name, value in fields.items():
        parts.append(f"{field_name}：{_format_field_value(value)}")
    return "；".join(parts)


# 这个函数把列表、字典等字段值转换成适合展示的短文本。
def _format_field_value(value: Any) -> str:
    if isinstance(value, (dict, list)):
        return json.dumps(value, ensure_ascii=False)
    return str(value)


# 这个函数解析 JSON 对象，兼容模型返回 Markdown 代码块的情况。
def _load_json_object(content: str) -> dict[str, Any] | None:
    cleaned = content.strip()
    if cleaned.startswith("```"):
        cleaned = re.sub(r"^```(?:json)?", "", cleaned).strip()
        cleaned = re.sub(r"```$", "", cleaned).strip()
    try:
        loaded = json.loads(cleaned)
    except json.JSONDecodeError:
        return None
    return loaded if isinstance(loaded, dict) else None
