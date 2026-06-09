"""飞书字段缓存服务。"""

from __future__ import annotations

import hashlib
from typing import Any

try:
    from ..agents.shared.config import ThirdServiceConfig
    from ..runtime.factory import get_workflow_runtime_store
    from ..storage.factory import get_workflow_repository
except ImportError:
    from agents.shared.config import ThirdServiceConfig
    from runtime.factory import get_workflow_runtime_store
    from storage.factory import get_workflow_repository


# 这个函数根据 app_token、table_id 和 view_id 生成字段缓存定位信息。
def table_cache_identity(config: ThirdServiceConfig) -> tuple[str, str, str | None, str]:
    app_token = config.feishu_app_token or config.table_context["app_token"]
    table_id = config.feishu_table_id or config.table_context["table_id"]
    view_id = config.feishu_view_id or None
    app_token_hash = hashlib.sha256(app_token.encode("utf-8")).hexdigest()
    table_key = f"{app_token_hash}:{table_id}:{view_id or ''}"
    return app_token_hash, table_id, view_id, table_key


# 这个函数读取未过期的字段缓存，并还原成飞书字段定义列表。
def load_cached_fields(config: ThirdServiceConfig) -> list[dict[str, Any]]:
    app_token_hash, table_id, view_id, _ = table_cache_identity(config)
    repository = get_workflow_repository()
    cached_rows = repository.get_feishu_field_cache(app_token_hash, table_id, view_id)
    return [_cache_row_to_field(row) for row in cached_rows]


# 这个函数把真实飞书字段定义写入缓存。
def save_cached_fields(config: ThirdServiceConfig, fields: list[dict[str, Any]]) -> None:
    app_token_hash, table_id, view_id, _ = table_cache_identity(config)
    repository = get_workflow_repository()
    repository.replace_feishu_field_cache(app_token_hash, table_id, view_id, fields, config.feishu_field_cache_ttl_seconds)


# 这个函数尝试获取字段刷新锁，避免多个 worker 同时刷新同一张表字段。
def acquire_field_refresh_lock(config: ThirdServiceConfig) -> bool:
    _, _, _, table_key = table_cache_identity(config)
    runtime_store = get_workflow_runtime_store()
    return runtime_store.acquire_schema_refresh_lock(table_key)


# 这个函数把缓存行还原成 Tool 需要的字段定义格式。
def _cache_row_to_field(row: dict[str, Any]) -> dict[str, Any]:
    field_type: Any = row.get("field_type")
    if isinstance(field_type, str) and field_type.isdigit():
        field_type = int(field_type)
    return {
        "field_id": row.get("field_id"),
        "field_name": row.get("field_name"),
        "type": field_type,
        "property": row.get("property_json") or {},
        "writable": row.get("writable", True),
        "readonly_reason": row.get("readonly_reason"),
    }
