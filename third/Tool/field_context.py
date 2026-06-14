"""飞书多维表格 Tool 使用的字段上下文读取服务。"""

from __future__ import annotations

from typing import Any

try:
    from ..agents.shared.config import ThirdServiceConfig, load_config
    from ..agents.shared.time_utils import now_iso
    from ..workflow.field_cache import acquire_field_refresh_lock, load_cached_fields, save_cached_fields
    from .mock_repository import list_mock_field_definitions
except ImportError:
    from agents.shared.config import ThirdServiceConfig, load_config
    from agents.shared.time_utils import now_iso
    from workflow.field_cache import acquire_field_refresh_lock, load_cached_fields, save_cached_fields
    from Tool.mock_repository import list_mock_field_definitions

from .feishu_client import FeishuBitableClient, FeishuClientError


# 这个函数是字段上下文入口，Tool 会先读取当前表字段再整理查询请求。
def load_table_fields_context() -> dict[str, Any]:
    config = load_config()
    table_context = config.table_context
    base_context = {
        "service": "feishu_bitable",
        "app_token": table_context["app_token"],
        "table_id": table_context["table_id"],
        "table_name": table_context["table_name"],
        "loaded_at": now_iso(),
    }

    if config.feishu_use_real:
        return _load_real_table_fields(config, base_context)
    return _load_mock_table_fields(base_context)


# 这个函数读取真实飞书表字段，失败时把错误放进上下文而不是中断整张图。
def _load_real_table_fields(config: ThirdServiceConfig, base_context: dict[str, Any]) -> dict[str, Any]:
    if not config.can_read_real_feishu:
        return {
            **base_context,
            "source": "config_error",
            "fields": [],
            "field_names": [],
            "error": f"真实飞书字段读取配置不完整，缺少：{'、'.join(config.missing_real_feishu_fields)}",
        }

    cached_fields = _load_cached_real_fields(config)
    if cached_fields:
        return {
            **base_context,
            "source": "feishu",
            "fields": cached_fields,
            "field_names": [field["field_name"] for field in cached_fields],
            "error": None,
            "cache": "hit",
        }

    try:
        acquire_field_refresh_lock(config)
        client = FeishuBitableClient(config)
        fields = client.list_field_definitions(config.feishu_app_token, config.feishu_table_id)
        save_cached_fields(config, fields)
    except FeishuClientError as exc:
        return {
            **base_context,
            "source": "feishu_error",
            "fields": [],
            "field_names": [],
            "error": str(exc),
        }

    return {
        **base_context,
        "source": "feishu",
        "fields": fields,
        "field_names": [field["field_name"] for field in fields],
        "error": None,
        "cache": "refresh",
    }


# 这个函数读取未过期的真实飞书字段缓存，缓存异常时不阻断字段读取。
def _load_cached_real_fields(config: ThirdServiceConfig) -> list[dict[str, Any]]:
    try:
        return load_cached_fields(config)
    except Exception:
        return []


# 这个函数在 mock 模式下从 mock 记录推导字段上下文，保持 LangSmith 调试可用。
def _load_mock_table_fields(base_context: dict[str, Any]) -> dict[str, Any]:
    fields = _mock_field_definitions()
    return {
        **base_context,
        "source": "mock",
        "fields": fields,
        "field_names": [field["field_name"] for field in fields],
        "error": None,
    }


# 这个函数把 mock 记录里的 fields 转换成类似飞书字段接口的定义。
def _mock_field_definitions() -> list[dict[str, Any]]:
    return list_mock_field_definitions()
