"""Router Agent：把自然语言整理成第三方服务结构化请求。"""

from __future__ import annotations

import json
import re
from typing import Any, Literal

from ..shared.config import ThirdServiceConfig, load_config
from ..shared.feishu_schema import DEFAULT_READ_FIELDS, FEISHU_READ_FIELD_SCHEMA, KNOWN_FIELD_ALIASES
from ..shared.time_utils import now_iso


# 这一段定义 Router 支持的意图类型，后续新增写入、更新、删除 Agent 时可以继续复用。
Intent = Literal["read", "write", "update", "delete", "clarify", "irrelevant"]


# 这一段是轻量规则路由的关键词，LLM 不可用时依然可以稳定跑通 LangGraph。
READ_KEYWORDS = ("查询", "读取", "搜索", "查找", "查", "找", "列出", "获取", "看看", "看一下", "显示")
WRITE_KEYWORDS = ("新增", "添加", "创建", "写入", "记录一下", "保存")
UPDATE_KEYWORDS = ("修改", "更新", "改成", "调整")
DELETE_KEYWORDS = ("删除", "移除", "清理")
IRRELEVANT_KEYWORDS = ("天气", "笑话", "翻译", "闲聊")


# 这个函数是 Router Agent 的入口，LangGraph 的 router_node 会调用它。
def route_user_input(user_input: str) -> dict[str, Any]:
    config = load_config()
    cleaned = _clean_text(user_input)
    llm_decision = _try_llm_route(cleaned, config)
    if llm_decision:
        return _normalize_decision(cleaned, llm_decision, config, source="llm")

    decision = _rule_based_route(cleaned, config)
    return _normalize_decision(cleaned, decision, config, source="rules")


# 这个函数清理用户输入中的多余空白，降低后续规则匹配的噪声。
def _clean_text(text: str) -> str:
    return re.sub(r"\s+", " ", (text or "").strip())


# 这个函数在没有 LLM 或不启用 LLM 时，用规则把自然语言路由成结构化请求。
def _rule_based_route(user_input: str, config: ThirdServiceConfig) -> dict[str, Any]:
    lower_input = user_input.lower()
    intent = _detect_intent(user_input, lower_input)

    read_request = None
    if intent == "read":
        read_request = _build_read_request(user_input, config)

    return {
        "intent": intent,
        "confidence": _confidence_for_intent(intent, user_input),
        "target_service": "feishu_bitable" if intent in {"read", "write", "update", "delete"} else None,
        "normalized_query": user_input,
        "read_request": read_request,
        "missing_fields": _missing_fields(intent, read_request, config),
        "reason": _reason_for_intent(intent),
    }


# 这个函数根据关键词判断意图，当前只让 read 意图进入 Read Agent。
def _detect_intent(user_input: str, lower_input: str) -> Intent:
    if not user_input:
        return "clarify"
    if any(keyword in user_input for keyword in IRRELEVANT_KEYWORDS):
        return "irrelevant"
    if any(keyword in user_input for keyword in DELETE_KEYWORDS):
        return "delete"
    if any(keyword in user_input for keyword in UPDATE_KEYWORDS):
        return "update"
    if any(keyword in user_input for keyword in WRITE_KEYWORDS):
        return "write"
    if any(keyword in user_input for keyword in READ_KEYWORDS):
        return "read"
    if any(token in lower_input for token in ("read", "search", "list", "get")):
        return "read"
    return "clarify"


# 这个函数给路由结果补充置信度，方便 LangSmith 里观察路由质量。
def _confidence_for_intent(intent: Intent, user_input: str) -> float:
    if intent == "clarify":
        return 0.35
    if intent == "irrelevant":
        return 0.6
    if intent == "read" and _extract_record_id(user_input):
        return 0.88
    if intent == "read":
        return 0.82
    return 0.7


# 这个函数说明路由原因，后续可以直接展示给调试界面。
def _reason_for_intent(intent: Intent) -> str:
    reasons = {
        "read": "用户表达了查询、读取、列出或获取记录的需求。",
        "write": "用户表达了新增或写入记录的需求，当前图暂未接入写入子 Agent。",
        "update": "用户表达了修改记录的需求，当前图暂未接入修改子 Agent。",
        "delete": "用户表达了删除记录的需求，当前图暂未接入删除子 Agent。",
        "clarify": "用户意图不足以稳定路由，需要补充说明。",
        "irrelevant": "用户输入与飞书多维表格增删改查无关。",
    }
    return reasons[intent]


# 这个函数构造 Read Agent 需要的读取请求，字段贴近飞书查询记录接口。
def _build_read_request(user_input: str, config: ThirdServiceConfig) -> dict[str, Any]:
    table_context = config.table_context
    record_id = _extract_record_id(user_input)
    app_token = _extract_named_token(user_input, "app_token") or _extract_base_app_token(user_input)
    table_id = _extract_named_token(user_input, "table_id") or _extract_table_id(user_input)
    view_id = _extract_named_token(user_input, "view_id") or _extract_view_id(user_input)
    field_names = _extract_field_names(user_input)

    operation = "get_record" if record_id else "search_records"
    conditions = _extract_filter_conditions(user_input)

    return {
        "operation": operation,
        "service": "feishu_bitable",
        "app_token": app_token or table_context["app_token"],
        "table_id": table_id or table_context["table_id"],
        "table_name": table_context["table_name"],
        "record_id": record_id,
        "view_id": view_id or table_context["view_id"] or None,
        "field_names": field_names,
        "filter": {
            "conjunction": "and",
            "conditions": conditions,
        },
        "sort": _extract_sort(user_input),
        "page_size": _extract_page_size(user_input),
        "page_token": None,
        "user_id_type": table_context["user_id_type"],
        "automatic_fields": True,
        "mock": not config.feishu_use_real,
        "source_fields": FEISHU_READ_FIELD_SCHEMA,
        "router_note": "Router 已整理飞书读取字段；真实读取由 Read Agent 根据配置决定。",
    }


# 这个函数提取形如 app_token: xxx、table_id=xxx 的显式参数。
def _extract_named_token(user_input: str, name: str) -> str | None:
    pattern = rf"{re.escape(name)}\s*[:=：]\s*([A-Za-z0-9_\-]+)"
    match = re.search(pattern, user_input, flags=re.IGNORECASE)
    return match.group(1) if match else None


# 这个函数从飞书 base 链接里提取 app_token。
def _extract_base_app_token(user_input: str) -> str | None:
    match = re.search(r"/base/([A-Za-z0-9_\-]+)", user_input)
    return match.group(1) if match else None


# 这个函数提取 table_id，支持 table_id=tblxxx 或 表=tblxxx。
def _extract_table_id(user_input: str) -> str | None:
    match = re.search(r"(?:table=|table_id=|表=)(tbl[A-Za-z0-9_\-]+)", user_input, flags=re.IGNORECASE)
    return match.group(1) if match else None


# 这个函数提取 view_id，支持 view_id=vewxxx 或 视图=vewxxx。
def _extract_view_id(user_input: str) -> str | None:
    match = re.search(r"(?:view=|view_id=|视图=)(vew[A-Za-z0-9_\-]+)", user_input, flags=re.IGNORECASE)
    return match.group(1) if match else None


# 这个函数提取 record_id，识别显式参数或 rec 开头的记录 id。
def _extract_record_id(user_input: str) -> str | None:
    explicit = _extract_named_token(user_input, "record_id")
    if explicit:
        return explicit
    match = re.search(r"\b(rec[A-Za-z0-9_\-]+)\b", user_input)
    return match.group(1) if match else None


# 这个函数把用户提到的字段别名归一化成表格字段名。
def _extract_field_names(user_input: str) -> list[str]:
    fields: list[str] = []
    lower_input = user_input.lower()
    for field_name, aliases in KNOWN_FIELD_ALIASES.items():
        if any(alias.lower() in lower_input for alias in aliases):
            fields.append(field_name)

    explicit_match = re.search(r"(?:返回|输出|只看|只返回|字段)\s*[:：]?\s*([^，。；;]+)", user_input)
    if explicit_match:
        fields.extend(_split_explicit_fields(explicit_match.group(1)))

    deduped = _dedupe_keep_order(fields)
    return deduped or DEFAULT_READ_FIELDS.copy()


# 这个函数拆分“只返回标题、状态”这类显式字段列表。
def _split_explicit_fields(text: str) -> list[str]:
    parts = re.split(r"[,，、\s]+", text)
    normalized: list[str] = []
    alias_to_field = {
        alias.lower(): field_name
        for field_name, aliases in KNOWN_FIELD_ALIASES.items()
        for alias in (field_name, *aliases)
    }
    for part in parts:
        item = part.strip(" .。；;")
        if not item:
            continue
        normalized.append(alias_to_field.get(item.lower(), item))
    return normalized


# 这个函数提取状态、优先级、分类和关键词过滤条件。
def _extract_filter_conditions(user_input: str) -> list[dict[str, Any]]:
    conditions: list[dict[str, Any]] = []

    status_match = re.search(r"状态(?:为|是|=|：|:)?\s*([^\s，。；;]+)", user_input)
    if status_match:
        status_value = _normalize_condition_value(status_match.group(1), ["进行中", "已完成", "待开始", "未完成"])
        conditions.append({"field_name": "状态", "operator": "is", "value": status_value})
    else:
        for status in ("进行中", "已完成", "待开始", "未完成"):
            if status in user_input:
                conditions.append({"field_name": "状态", "operator": "is", "value": status})
                break

    priority_match = re.search(r"优先级(?:为|是|=|：|:)?\s*([高中低])", user_input)
    if priority_match:
        conditions.append({"field_name": "优先级", "operator": "is", "value": priority_match.group(1)})

    category_match = re.search(r"(?:分类|类别|类型)(?:为|是|=|：|:)?\s*([^\s，。；;]+)", user_input)
    if category_match:
        category_value = _normalize_condition_value(category_match.group(1), [])
        conditions.append({"field_name": "分类", "operator": "is", "value": category_value})

    keyword_match = re.search(r"(?:包含|关键词|搜索|查找)\s*[:：]?\s*([^\s，。；;]+)", user_input)
    if keyword_match:
        conditions.append({"field_name": "内容", "operator": "contains", "value": keyword_match.group(1)})

    return conditions


# 这个函数清理“进行中的记录”这类被自然语言后缀污染的条件值。
def _normalize_condition_value(value: str, known_values: list[str]) -> str:
    stripped = value.strip()
    for known_value in known_values:
        if known_value in stripped:
            return known_value
    return re.sub(r"(的)?记录$", "", stripped)


# 这个函数提取排序条件，当前支持最近、最早和截止时间排序。
def _extract_sort(user_input: str) -> list[dict[str, Any]]:
    if "最新" in user_input or "最近" in user_input:
        return [{"field_name": "更新时间", "desc": True}]
    if "最早" in user_input:
        return [{"field_name": "创建时间", "desc": False}]
    if "截止" in user_input or "到期" in user_input:
        return [{"field_name": "截止时间", "desc": False}]
    return []


# 这个函数提取分页大小，并限制在飞书查询记录接口允许的 1 到 500。
def _extract_page_size(user_input: str) -> int:
    match = re.search(r"(?:前|最多|返回)?\s*(\d{1,3})\s*(?:条|个)", user_input)
    if not match:
        return 20
    return max(1, min(int(match.group(1)), 500))


# 这个函数在真实读取模式下提示缺少的飞书配置。
def _missing_fields(intent: Intent, read_request: dict[str, Any] | None, config: ThirdServiceConfig) -> list[str]:
    if intent != "read" or not read_request or not config.feishu_use_real:
        return []
    return config.missing_real_feishu_fields


# 这个函数在保留顺序的同时去重字段名。
def _dedupe_keep_order(items: list[str]) -> list[str]:
    seen: set[str] = set()
    deduped: list[str] = []
    for item in items:
        if item not in seen:
            deduped.append(item)
            seen.add(item)
    return deduped


# 这个函数统一补齐路由结果，保证 LangSmith 里看到的状态结构稳定。
def _normalize_decision(
    user_input: str,
    decision: dict[str, Any],
    config: ThirdServiceConfig,
    source: str,
) -> dict[str, Any]:
    intent = decision.get("intent") or "clarify"
    if intent not in {"read", "write", "update", "delete", "clarify", "irrelevant"}:
        intent = "clarify"

    read_request = decision.get("read_request")
    if intent == "read" and not read_request:
        read_request = _build_read_request(user_input, config)

    return {
        "intent": intent,
        "confidence": float(decision.get("confidence") or 0.5),
        "target_service": decision.get("target_service") or ("feishu_bitable" if intent == "read" else None),
        "normalized_query": decision.get("normalized_query") or user_input,
        "read_request": read_request,
        "missing_fields": decision.get("missing_fields") or _missing_fields(intent, read_request, config),
        "reason": decision.get("reason") or _reason_for_intent(intent),
        "routed_at": now_iso(),
        "route_source": source,
    }


# 这个函数在你提供 OpenAI API Key 且启用 LLM 后，优先用模型做更强的字段整理。
def _try_llm_route(user_input: str, config: ThirdServiceConfig) -> dict[str, Any] | None:
    if not config.router_use_llm:
        return None
    try:
        from langchain_openai import ChatOpenAI
    except ImportError:
        return None
    if not config.openai_api_key:
        return None

    prompt = _router_prompt(user_input, config)
    model = ChatOpenAI(model=config.router_model, temperature=0, api_key=config.openai_api_key)
    response = model.invoke(prompt)
    content = getattr(response, "content", "")
    return _load_json_object(str(content))


# 这个函数生成 Router LLM 的约束提示词，要求它只输出 JSON。
def _router_prompt(user_input: str, config: ThirdServiceConfig) -> str:
    table_context = config.table_context
    return f"""
你是第三方服务 Router Agent。请把用户自然语言路由到飞书多维表格 CRUD 子 Agent。
当前只允许 read 子 Agent 继续执行，其他意图仍需结构化输出但不要伪装成 read。

飞书读取字段约束：
{json.dumps(FEISHU_READ_FIELD_SCHEMA, ensure_ascii=False, indent=2)}

filter.conditions[].operator 只能使用这些飞书合法值：
is, isNot, contains, doesNotContain, isEmpty, isNotEmpty, isGreater, isGreaterEqual, isLess, isLessEqual, like, in。
不要输出 equals；等于语义必须输出 is。

默认表上下文：
{json.dumps(table_context, ensure_ascii=False)}

输出严格 JSON，不要 Markdown。结构：
{{
  "intent": "read|write|update|delete|clarify|irrelevant",
  "confidence": 0.0,
  "target_service": "feishu_bitable 或 null",
  "normalized_query": "整理后的查询意图",
  "read_request": {{
    "operation": "search_records|get_record|list_records",
    "service": "feishu_bitable",
    "app_token": "...",
    "table_id": "...",
    "table_name": "...",
    "record_id": null,
    "view_id": null,
    "field_names": ["标题", "内容", "状态"],
    "filter": {{"conjunction": "and", "conditions": []}},
    "sort": [],
    "page_size": 20,
    "page_token": null,
    "user_id_type": "open_id",
    "automatic_fields": true,
    "mock": true
  }},
  "missing_fields": [],
  "reason": "路由原因"
}}

用户输入：{user_input}
""".strip()


# 这个函数从模型输出中解析 JSON，兼容模型偶尔包一层 Markdown 代码块的情况。
def _load_json_object(content: str) -> dict[str, Any] | None:
    content = content.strip()
    if content.startswith("```"):
        content = re.sub(r"^```(?:json)?", "", content).strip()
        content = re.sub(r"```$", "", content).strip()
    try:
        loaded = json.loads(content)
    except json.JSONDecodeError:
        return None
    return loaded if isinstance(loaded, dict) else None
