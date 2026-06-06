"""飞书多维表格真实读取客户端。"""

from __future__ import annotations

import json
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen

from ..shared.config import ThirdServiceConfig


# 这一段定义内部 operator 到飞书合法 operator 的兼容映射，防止 LLM 输出常见别名导致飞书 400。
FEISHU_OPERATOR_ALIASES = {
    "=": "is",
    "==": "is",
    "equals": "is",
    "equal": "is",
    "is": "is",
    "!=": "isNot",
    "not_equals": "isNot",
    "notEqual": "isNot",
    "is_not": "isNot",
    "isNot": "isNot",
    "contains": "contains",
    "doesNotContain": "doesNotContain",
    "does_not_contain": "doesNotContain",
    "not_contains": "doesNotContain",
    "isEmpty": "isEmpty",
    "is_empty": "isEmpty",
    "empty": "isEmpty",
    "isNotEmpty": "isNotEmpty",
    "is_not_empty": "isNotEmpty",
    "not_empty": "isNotEmpty",
    "exists": "isNotEmpty",
    ">": "isGreater",
    "greater_than": "isGreater",
    "isGreater": "isGreater",
    ">=": "isGreaterEqual",
    "greater_equal": "isGreaterEqual",
    "isGreaterEqual": "isGreaterEqual",
    "<": "isLess",
    "less_than": "isLess",
    "isLess": "isLess",
    "<=": "isLessEqual",
    "less_equal": "isLessEqual",
    "isLessEqual": "isLessEqual",
    "like": "like",
    "in": "in",
}


# 这一段定义不需要 value 的飞书空值判断 operator。
VALUELESS_OPERATORS = {"isEmpty", "isNotEmpty"}


# 这个异常表示飞书接口调用或响应解析失败，Read Agent 会捕获并输出到结果里。
class FeishuClientError(RuntimeError):
    pass


# 这个客户端只负责飞书 HTTP API，不处理自然语言，也不处理 LangGraph 状态。
class FeishuBitableClient:
    # 这个初始化方法接收集中配置，避免客户端直接读取环境变量。
    def __init__(self, config: ThirdServiceConfig) -> None:
        self.config = config

    # 这个方法根据 operation 分派到查询记录或检索单条记录。
    def read_records(self, request: dict[str, Any]) -> list[dict[str, Any]]:
        if request.get("operation") == "get_record" and request.get("record_id"):
            record = self.get_record(request)
            return [record] if record else []
        return self.search_records(request)

    # 这个方法调用飞书查询记录接口，支持 field_names、filter、sort 和分页。
    def search_records(self, request: dict[str, Any]) -> list[dict[str, Any]]:
        app_token = request["app_token"]
        table_id = request["table_id"]
        available_fields = self.list_fields(app_token, table_id)
        _prepare_request_fields_for_real_table(request, available_fields, self.config.feishu_field_name_map)
        query = _clean_query_params(
            {
                "page_size": min(int(request.get("page_size") or 20), 500),
                "page_token": request.get("page_token"),
                "user_id_type": request.get("user_id_type") or self.config.feishu_user_id_type,
            }
        )
        url = _with_query(
            f"https://open.feishu.cn/open-apis/bitable/v1/apps/{app_token}/tables/{table_id}/records/search",
            query,
        )
        body = _clean_body(
            {
                "view_id": request.get("view_id"),
                "field_names": request.get("field_names"),
                "sort": _to_feishu_sort(request.get("sort", [])),
                "filter": _to_feishu_filter(request.get("filter")),
                "automatic_fields": request.get("automatic_fields", True),
            }
        )
        response = self._post_json(url, body, with_auth=True)
        items = response.get("data", {}).get("items", [])
        return [_normalize_feishu_record(item) for item in items]

    # 这个方法调用飞书列出字段接口，读取真实表字段名，用于查询前校验字段。
    def list_fields(self, app_token: str, table_id: str) -> list[str]:
        field_names: list[str] = []
        page_token = None
        while True:
            query = _clean_query_params({"page_size": 100, "page_token": page_token})
            url = _with_query(
                f"https://open.feishu.cn/open-apis/bitable/v1/apps/{app_token}/tables/{table_id}/fields",
                query,
            )
            response = self._get_json(url, with_auth=True)
            data = response.get("data", {})
            for item in data.get("items", []):
                field_name = item.get("field_name")
                if field_name:
                    field_names.append(str(field_name))
            if not data.get("has_more"):
                return field_names
            page_token = data.get("page_token")

    # 这个方法调用飞书检索单条记录接口，用于用户明确给出 record_id 的场景。
    def get_record(self, request: dict[str, Any]) -> dict[str, Any] | None:
        app_token = request["app_token"]
        table_id = request["table_id"]
        record_id = request["record_id"]
        query = _clean_query_params({"user_id_type": request.get("user_id_type") or self.config.feishu_user_id_type})
        url = _with_query(
            f"https://open.feishu.cn/open-apis/bitable/v1/apps/{app_token}/tables/{table_id}/records/{record_id}",
            query,
        )
        response = self._get_json(url, with_auth=True)
        record = response.get("data", {}).get("record")
        return _normalize_feishu_record(record) if record else None

    # 这个方法获取 tenant_access_token；如果你直接配置了 token，就不会再请求飞书鉴权接口。
    def _tenant_access_token(self) -> str:
        if self.config.feishu_tenant_access_token:
            return self.config.feishu_tenant_access_token

        url = "https://open.feishu.cn/open-apis/auth/v3/tenant_access_token/internal"
        body = {
            "app_id": self.config.feishu_app_id,
            "app_secret": self.config.feishu_app_secret,
        }
        response = self._post_json(url, body, with_auth=False)
        token = response.get("tenant_access_token")
        if not token:
            raise FeishuClientError(f"飞书 tenant_access_token 响应缺少 token：{response}")
        return str(token)

    # 这个方法发送 POST JSON 请求，并统一检查飞书 code。
    def _post_json(self, url: str, body: dict[str, Any], with_auth: bool) -> dict[str, Any]:
        headers = {"Content-Type": "application/json; charset=utf-8"}
        if with_auth:
            headers["Authorization"] = f"Bearer {self._tenant_access_token()}"
        data = json.dumps(body, ensure_ascii=False).encode("utf-8")
        request = Request(url=url, data=data, headers=headers, method="POST")
        return self._open_json(request)

    # 这个方法发送 GET 请求，并统一检查飞书 code。
    def _get_json(self, url: str, with_auth: bool) -> dict[str, Any]:
        headers = {"Content-Type": "application/json; charset=utf-8"}
        if with_auth:
            headers["Authorization"] = f"Bearer {self._tenant_access_token()}"
        request = Request(url=url, headers=headers, method="GET")
        return self._open_json(request)

    # 这个方法执行 HTTP 请求并解析 JSON 响应。
    def _open_json(self, request: Request) -> dict[str, Any]:
        try:
            with urlopen(request, timeout=20) as response:
                payload = json.loads(response.read().decode("utf-8"))
        except HTTPError as exc:
            body = exc.read().decode("utf-8", errors="replace")
            raise FeishuClientError(_format_http_error(exc.code, body)) from exc
        except URLError as exc:
            raise FeishuClientError(f"飞书网络请求失败：{exc.reason}") from exc
        except json.JSONDecodeError as exc:
            raise FeishuClientError("飞书响应不是合法 JSON。") from exc

        code = payload.get("code", 0)
        if code != 0:
            raise FeishuClientError(f"飞书接口返回错误 code={code}, msg={payload.get('msg')}")
        return payload


# 这个函数把内部过滤条件转换成飞书 search records 接口的 filter 结构。
def _to_feishu_filter(filter_config: dict[str, Any] | None) -> dict[str, Any] | None:
    if not filter_config:
        return None
    conditions = []
    for condition in filter_config.get("conditions", []):
        converted = _to_feishu_condition(condition)
        if converted:
            conditions.append(converted)
    if not conditions:
        return None
    return {
        "conjunction": filter_config.get("conjunction", "and"),
        "conditions": conditions,
    }


# 这个函数根据真实飞书字段名校验并改写读取请求，避免 FieldNameNotFound。
def _prepare_request_fields_for_real_table(
    request: dict[str, Any],
    available_fields: list[str],
    field_name_map: dict[str, str],
) -> None:
    available_set = set(available_fields)
    validation = {
        "available_field_names": available_fields,
        "mapped_field_names": {},
        "dropped_field_names": [],
        "dropped_filter_conditions": [],
        "dropped_sort_rules": [],
    }

    request["field_names"] = _prepare_field_names(
        request.get("field_names", []),
        available_set,
        field_name_map,
        validation,
    )
    request["filter"] = _prepare_filter(
        request.get("filter"),
        available_set,
        field_name_map,
        validation,
    )
    request["sort"] = _prepare_sort(
        request.get("sort", []),
        available_set,
        field_name_map,
        validation,
    )
    request["field_validation"] = validation


# 这个函数校验返回字段；如果全部不匹配，就清空 field_names 让飞书返回全部字段。
def _prepare_field_names(
    field_names: list[str],
    available_fields: set[str],
    field_name_map: dict[str, str],
    validation: dict[str, Any],
) -> list[str]:
    prepared: list[str] = []
    for field_name in field_names or []:
        resolved = _resolve_field_name(field_name, available_fields, field_name_map, validation)
        if resolved:
            prepared.append(resolved)
        else:
            validation["dropped_field_names"].append(field_name)
    return _dedupe_keep_order(prepared)


# 这个函数校验过滤条件；未知字段的过滤条件会被移除并记录原因。
def _prepare_filter(
    filter_config: dict[str, Any] | None,
    available_fields: set[str],
    field_name_map: dict[str, str],
    validation: dict[str, Any],
) -> dict[str, Any]:
    if not filter_config:
        return {"conjunction": "and", "conditions": []}

    conditions: list[dict[str, Any]] = []
    for condition in filter_config.get("conditions", []):
        field_name = condition.get("field_name")
        resolved = _resolve_field_name(field_name, available_fields, field_name_map, validation)
        if not resolved:
            validation["dropped_filter_conditions"].append(condition)
            continue
        prepared_condition = dict(condition)
        prepared_condition["field_name"] = resolved
        conditions.append(prepared_condition)
    return {
        "conjunction": filter_config.get("conjunction", "and"),
        "conditions": conditions,
    }


# 这个函数校验排序字段；未知字段的排序规则会被移除并记录原因。
def _prepare_sort(
    sort_rules: list[dict[str, Any]],
    available_fields: set[str],
    field_name_map: dict[str, str],
    validation: dict[str, Any],
) -> list[dict[str, Any]]:
    prepared_rules: list[dict[str, Any]] = []
    for rule in sort_rules or []:
        field_name = rule.get("field_name")
        resolved = _resolve_field_name(field_name, available_fields, field_name_map, validation)
        if not resolved:
            validation["dropped_sort_rules"].append(rule)
            continue
        prepared_rule = dict(rule)
        prepared_rule["field_name"] = resolved
        prepared_rules.append(prepared_rule)
    return prepared_rules


# 这个函数把项目字段名解析成真实飞书字段名，优先使用显式映射，再尝试精确匹配。
def _resolve_field_name(
    field_name: Any,
    available_fields: set[str],
    field_name_map: dict[str, str],
    validation: dict[str, Any],
) -> str | None:
    if not field_name:
        return None
    original = str(field_name).strip()
    mapped = field_name_map.get(original, original).strip()
    if mapped in available_fields:
        if mapped != original:
            validation["mapped_field_names"][original] = mapped
        return mapped

    normalized_available = {field.strip(): field for field in available_fields}
    if mapped in normalized_available:
        resolved = normalized_available[mapped]
        if resolved != original:
            validation["mapped_field_names"][original] = resolved
        return resolved
    return None


# 这个函数转换单个过滤条件，保证 operator 和 value 都符合飞书接口格式。
def _to_feishu_condition(condition: dict[str, Any]) -> dict[str, Any] | None:
    field_name = condition.get("field_name")
    if not field_name:
        return None

    operator = _normalize_operator(condition.get("operator"))
    value = condition.get("value")
    converted = {
        "field_name": field_name,
        "operator": operator,
    }
    if operator in VALUELESS_OPERATORS:
        return converted
    if value in (None, ""):
        return None
    converted["value"] = value if isinstance(value, list) else [value]
    return converted


# 这个函数把 equals、not_empty 等内部或 LLM 常见表达映射为飞书合法 operator。
def _normalize_operator(operator: Any) -> str:
    normalized = str(operator or "is").strip()
    return FEISHU_OPERATOR_ALIASES.get(normalized, "is")


# 这个函数把内部排序条件转换成飞书 search records 接口的 sort 结构。
def _to_feishu_sort(sort_rules: list[dict[str, Any]]) -> list[dict[str, Any]]:
    converted: list[dict[str, Any]] = []
    for rule in sort_rules or []:
        field_name = rule.get("field_name")
        if not field_name:
            continue
        converted.append({"field_name": field_name, "desc": bool(rule.get("desc"))})
    return converted


# 这个函数去掉 query 参数里的空值。
def _clean_query_params(params: dict[str, Any]) -> dict[str, Any]:
    return {key: value for key, value in params.items() if value not in (None, "")}


# 这个函数去掉请求体里的空值，避免飞书接口收到无意义字段。
def _clean_body(body: dict[str, Any]) -> dict[str, Any]:
    return {key: value for key, value in body.items() if value not in (None, "", [], {})}


# 这个函数把基础 URL 和 query 参数组合成最终请求 URL。
def _with_query(url: str, params: dict[str, Any]) -> str:
    if not params:
        return url
    return f"{url}?{urlencode(params)}"


# 这个函数把飞书 record 响应归一化成 Read Agent 的标准记录结构。
def _normalize_feishu_record(record: dict[str, Any]) -> dict[str, Any]:
    return {
        "record_id": record.get("record_id"),
        "fields": record.get("fields", {}),
    }


# 这个函数在保留顺序的同时去重字段名。
def _dedupe_keep_order(items: list[str]) -> list[str]:
    seen: set[str] = set()
    deduped: list[str] = []
    for item in items:
        if item not in seen:
            deduped.append(item)
            seen.add(item)
    return deduped


# 这个函数把飞书 HTTP 错误整理成更容易读的中文信息。
def _format_http_error(status_code: int, body: str) -> str:
    try:
        payload = json.loads(body)
    except json.JSONDecodeError:
        return f"飞书 HTTP {status_code}：{body}"

    code = payload.get("code")
    message = payload.get("msg")
    violations = payload.get("error", {}).get("field_violations", [])
    if not violations:
        return f"飞书 HTTP {status_code}：code={code}, msg={message}"

    details = []
    for violation in violations:
        field = violation.get("field")
        value = violation.get("value")
        description = violation.get("description")
        details.append(f"{field}={value}，{description}")
    return f"飞书 HTTP {status_code}：code={code}, msg={message}；字段校验失败：{'；'.join(details)}"
