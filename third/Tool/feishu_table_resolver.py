"""把飞书多维表格 Base/Wiki URL 解析成统一表定位信息。"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any
from urllib.parse import parse_qs, unquote, urlparse

from .feishu_client import FeishuBitableClient, FeishuClientError

try:
    from ..agents.shared.config import ThirdServiceConfig
except ImportError:
    from agents.shared.config import ThirdServiceConfig


FEISHU_URL_INVALID = "FEISHU_URL_INVALID"
FEISHU_WIKI_NOT_BITABLE = "FEISHU_WIKI_NOT_BITABLE"
FEISHU_WIKI_PERMISSION_DENIED = "FEISHU_WIKI_PERMISSION_DENIED"
FEISHU_WIKI_RESOLVE_FAILED = "FEISHU_WIKI_RESOLVE_FAILED"
_TOKEN_PATTERN = re.compile(r"^[A-Za-z0-9_-]+$")


class FeishuTableResolveError(RuntimeError):
    def __init__(self, error_code: str, message: str) -> None:
        super().__init__(message)
        self.error_code = error_code


@dataclass(frozen=True)
class ResolvedFeishuTable:
    source_type: str
    app_token: str
    table_id: str
    view_id: str


def resolve_feishu_table_url(table_url: str, config: ThirdServiceConfig) -> ResolvedFeishuTable:
    parsed = _parse_url(table_url)
    source_type, source_token = _source_from_path(parsed.path)
    query = parse_qs(parsed.query, keep_blank_values=True)
    table_id = _first_query_value(query, "table", "table_id")
    view_id = _first_query_value(query, "view", "view_id") or ""
    if not table_id:
        raise FeishuTableResolveError(
            FEISHU_URL_INVALID,
            "飞书 URL 缺少 table 参数，请从具体多维表格视图复制链接。",
        )
    _validate_token(table_id, "table")
    if view_id:
        _validate_token(view_id, "view")

    if source_type == "base":
        return ResolvedFeishuTable("base", source_token, table_id, view_id)

    if not str(parsed.hostname or "").lower().endswith(".feishu.cn"):
        raise FeishuTableResolveError(
            FEISHU_URL_INVALID,
            "当前只支持 feishu.cn 的 Wiki 多维表格链接。",
        )
    if not config.feishu_tenant_access_token and not (config.feishu_app_id and config.feishu_app_secret):
        raise FeishuTableResolveError(
            FEISHU_WIKI_RESOLVE_FAILED,
            "解析 Wiki 多维表格需要有效的飞书 App ID、App Secret 或 tenant access token。",
        )

    try:
        node = FeishuBitableClient(config).get_wiki_node(source_token)
    except FeishuClientError as exc:
        message = str(exc)
        permission_markers = ("code=131006", "code=99991663", "code=99991672", "HTTP 403")
        if any(marker in message for marker in permission_markers) or "permission denied" in message.lower():
            raise FeishuTableResolveError(
                FEISHU_WIKI_PERMISSION_DENIED,
                "无法读取飞书 Wiki 节点，请为应用开通 wiki:node:read 并授予目标节点阅读权限。",
            ) from exc
        raise FeishuTableResolveError(
            FEISHU_WIKI_RESOLVE_FAILED,
            f"飞书 Wiki 节点解析失败：{message}",
        ) from exc

    if str(node.get("obj_type") or "").lower() != "bitable":
        raise FeishuTableResolveError(
            FEISHU_WIKI_NOT_BITABLE,
            "该 Wiki 链接指向的不是飞书多维表格。",
        )
    app_token = str(node.get("obj_token") or "").strip()
    if not app_token:
        raise FeishuTableResolveError(
            FEISHU_WIKI_RESOLVE_FAILED,
            "飞书 Wiki 节点响应缺少多维表格 obj_token。",
        )
    _validate_token(app_token, "obj_token", FEISHU_WIKI_RESOLVE_FAILED)
    return ResolvedFeishuTable("wiki", app_token, table_id, view_id)


def resolve_response(table_url: str, config: ThirdServiceConfig) -> dict[str, Any]:
    try:
        resolved = resolve_feishu_table_url(table_url, config)
    except FeishuTableResolveError as exc:
        return {
            "status": "error",
            "error_code": exc.error_code,
            "message": str(exc),
        }
    return {
        "status": "ok",
        "error_code": None,
        "message": "飞书多维表格 URL 解析成功。",
        "source_type": resolved.source_type,
        "app_token": resolved.app_token,
        "table_id": resolved.table_id,
        "view_id": resolved.view_id,
    }


def _parse_url(value: str):
    raw_value = str(value or "").strip()
    if not raw_value:
        raise FeishuTableResolveError(FEISHU_URL_INVALID, "请填写飞书多维表格 URL。")
    try:
        parsed = urlparse(raw_value)
    except ValueError as exc:
        raise FeishuTableResolveError(FEISHU_URL_INVALID, "飞书多维表格 URL 格式不正确。") from exc
    if parsed.scheme.lower() != "https":
        raise FeishuTableResolveError(FEISHU_URL_INVALID, "飞书多维表格 URL 必须使用 HTTPS。")
    host = str(parsed.hostname or "").lower()
    if not (host.endswith(".feishu.cn") or host.endswith(".larksuite.com")):
        raise FeishuTableResolveError(
            FEISHU_URL_INVALID,
            "只支持 feishu.cn 或 larksuite.com 的多维表格 URL。",
        )
    return parsed


def _source_from_path(path: str) -> tuple[str, str]:
    segments = [unquote(segment).strip() for segment in str(path or "").split("/") if segment.strip()]
    for index, segment in enumerate(segments[:-1]):
        if segment in {"base", "wiki"}:
            token = segments[index + 1]
            _validate_token(token, segment)
            return segment, token
    raise FeishuTableResolveError(
        FEISHU_URL_INVALID,
        "飞书 URL 缺少 /base/{appToken} 或 /wiki/{nodeToken}。",
    )


def _first_query_value(query: dict[str, list[str]], *keys: str) -> str | None:
    for key in keys:
        for value in query.get(key, []):
            normalized = str(value or "").strip()
            if normalized:
                return normalized
    return None


def _validate_token(value: str, name: str, error_code: str = FEISHU_URL_INVALID) -> None:
    if not value or not _TOKEN_PATTERN.fullmatch(value):
        raise FeishuTableResolveError(error_code, f"飞书 URL 中的 {name} 参数格式不正确。")
