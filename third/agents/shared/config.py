"""第三方服务模块的环境变量配置。"""

from __future__ import annotations

import os
import json
from contextlib import contextmanager
from contextvars import ContextVar
from dataclasses import dataclass
from dataclasses import replace
from pathlib import Path
from typing import Any

from sqlalchemy.engine import make_url


# 这一段定义 mock 表格的默认定位信息，用于还没有接入真实飞书时继续验证 LangGraph。
DEFAULT_APP_TOKEN = "app_mock_for_mygirl"
DEFAULT_TABLE_ID = "tbl_mock_records"
DEFAULT_TABLE_NAME = "项目记录"
THIRD_ALLOWED_MYSQL_DATABASES = {"third_service", "third_test"}
THIRD_FORBIDDEN_MYSQL_DATABASES = {"for_mygirl_app"}
THIRD_FORBIDDEN_MYSQL_USERS = {"backend_user"}
_PRIVATE_METADATA: ContextVar[dict[str, Any] | None] = ContextVar("third_private_metadata", default=None)


# 这个数据类集中管理飞书、OpenAI、MySQL、Redis 和 workflow 所需配置，避免配置散落在各个文件里。
@dataclass(frozen=True)
class ThirdServiceConfig:
    feishu_app_id: str
    feishu_app_secret: str
    feishu_tenant_access_token: str
    feishu_app_token: str
    feishu_table_id: str
    feishu_table_name: str
    feishu_view_id: str
    feishu_user_id_type: str
    feishu_use_real: bool
    openai_api_key: str
    openai_proxy_url: str
    news_focus_proxy_url: str
    openai_timeout_seconds: int
    openai_max_retries: int
    llm_route_mode: str
    llm_fallback_providers: list[str]
    llm_probe_enabled: bool
    llm_probe_ttl_seconds: int
    llm_probe_samples: int
    llm_probe_min_successes: int
    llm_unhealthy_ttl_seconds: int
    deepseek_api_key: str
    deepseek_base_url: str
    deepseek_model: str
    deepseek_timeout_seconds: int
    deepseek_max_retries: int
    minimax_api_key: str
    minimax_base_url: str
    minimax_model: str
    minimax_timeout_seconds: int
    minimax_max_retries: int
    workflowagent_use_llm: bool
    workflowagent_model: str
    mysql_dsn: str
    redis_url: str
    workflow_queue_name: str
    workflow_consumer_group: str
    workflow_consumer_name: str
    workflow_lock_ttl_seconds: int
    workflow_pending_idle_ms: int
    workflow_max_deliveries: int
    workflow_dead_letter_queue_name: str
    workflow_artifact_ttl_seconds: int
    workflow_idempotency_ttl_seconds: int
    feishu_field_cache_ttl_seconds: int
    allow_in_memory_fallback: bool
    debug_enabled: bool
    workflow_debug_log: bool
    feishu_field_name_map: dict[str, str]

    # 这个属性判断真实飞书读取是否具备最小配置。
    @property
    def can_read_real_feishu(self) -> bool:
        has_access_token = bool(self.feishu_tenant_access_token)
        has_app_credentials = bool(self.feishu_app_id and self.feishu_app_secret)
        has_table_location = bool(self.feishu_app_token and self.feishu_table_id)
        return has_table_location and (has_access_token or has_app_credentials)

    # 这个属性判断真实飞书写入是否具备最小配置；接口权限由飞书侧返回 403 时确认。
    @property
    def can_write_real_feishu(self) -> bool:
        return self.can_read_real_feishu

    # 这个属性列出真实飞书读取缺少的配置，便于 LangSmith 里直接定位问题。
    @property
    def missing_real_feishu_fields(self) -> list[str]:
        missing: list[str] = []
        if not self.feishu_app_token:
            missing.append("THIRD_FEISHU_APP_TOKEN")
        if not self.feishu_table_id:
            missing.append("THIRD_FEISHU_TABLE_ID")
        if not self.feishu_tenant_access_token and not (self.feishu_app_id and self.feishu_app_secret):
            missing.extend(["THIRD_FEISHU_APP_ID", "THIRD_FEISHU_APP_SECRET"])
        return missing

    # 这个属性给 Tool 使用，提供默认表格上下文。
    @property
    def table_context(self) -> dict[str, str]:
        app_token = self.feishu_app_token if self.feishu_use_real else self.feishu_app_token or DEFAULT_APP_TOKEN
        table_id = self.feishu_table_id if self.feishu_use_real else self.feishu_table_id or DEFAULT_TABLE_ID
        return {
            "app_token": app_token,
            "table_id": table_id,
            "table_name": self.feishu_table_name or DEFAULT_TABLE_NAME,
            "view_id": self.feishu_view_id,
            "user_id_type": self.feishu_user_id_type,
        }

    @property
    def deepseek_ready(self) -> bool:
        return bool(self.deepseek_api_key and self.deepseek_base_url and self.deepseek_model)

    @property
    def minimax_ready(self) -> bool:
        return bool(self.minimax_api_key and self.minimax_base_url and self.minimax_model)

    @property
    def has_usable_llm_provider(self) -> bool:
        has_primary = bool(self.openai_api_key and self.workflowagent_model)
        return has_primary or self.deepseek_ready or self.minimax_ready


# 这个函数从环境变量和 .env 文件创建配置对象；你后续收集到真实信息后只需要填配置。
def load_config(private_metadata: dict[str, Any] | None = None) -> ThirdServiceConfig:
    _load_env_files()
    debug_enabled = _read_bool("THIRD_DEBUG_ENABLED", default=True)
    config = ThirdServiceConfig(
        feishu_app_id=os.getenv("THIRD_FEISHU_APP_ID", ""),
        feishu_app_secret=os.getenv("THIRD_FEISHU_APP_SECRET", ""),
        feishu_tenant_access_token=os.getenv("THIRD_FEISHU_TENANT_ACCESS_TOKEN", ""),
        feishu_app_token=os.getenv("THIRD_FEISHU_APP_TOKEN", ""),
        feishu_table_id=os.getenv("THIRD_FEISHU_TABLE_ID", ""),
        feishu_table_name=os.getenv("THIRD_FEISHU_TABLE_NAME", DEFAULT_TABLE_NAME),
        feishu_view_id=os.getenv("THIRD_FEISHU_VIEW_ID", ""),
        feishu_user_id_type=os.getenv("THIRD_FEISHU_USER_ID_TYPE", "open_id"),
        feishu_use_real=_read_bool("THIRD_FEISHU_USE_REAL", default=False),
        openai_api_key=os.getenv("OPENAI_API_KEY", ""),
        openai_proxy_url=os.getenv("THIRD_OPENAI_PROXY_URL", ""),
        news_focus_proxy_url=os.getenv("THIRD_NEWS_FOCUS_PROXY_URL", "").strip(),
        openai_timeout_seconds=_read_int("THIRD_OPENAI_TIMEOUT_SECONDS", 60),
        openai_max_retries=_read_int("THIRD_OPENAI_MAX_RETRIES", 2),
        llm_route_mode=os.getenv("THIRD_LLM_ROUTE_MODE", "auto").strip().lower() or "auto",
        llm_fallback_providers=_read_csv("THIRD_LLM_FALLBACK_PROVIDERS", ["deepseek", "minimax"]),
        llm_probe_enabled=_read_bool("THIRD_LLM_PROBE_ENABLED", default=True),
        llm_probe_ttl_seconds=_read_int("THIRD_LLM_PROBE_TTL_SECONDS", 60),
        llm_probe_samples=_read_int("THIRD_LLM_PROBE_SAMPLES", 3),
        llm_probe_min_successes=_read_int("THIRD_LLM_PROBE_MIN_SUCCESSES", 2),
        llm_unhealthy_ttl_seconds=_read_int("THIRD_LLM_UNHEALTHY_TTL_SECONDS", 120),
        deepseek_api_key=os.getenv("THIRD_DEEPSEEK_API_KEY", ""),
        deepseek_base_url=os.getenv("THIRD_DEEPSEEK_BASE_URL", ""),
        deepseek_model=os.getenv("THIRD_DEEPSEEK_MODEL", ""),
        deepseek_timeout_seconds=_read_int("THIRD_DEEPSEEK_TIMEOUT_SECONDS", 60),
        deepseek_max_retries=_read_int("THIRD_DEEPSEEK_MAX_RETRIES", 0),
        minimax_api_key=os.getenv("THIRD_MINIMAX_API_KEY", ""),
        minimax_base_url=os.getenv("THIRD_MINIMAX_BASE_URL", ""),
        minimax_model=os.getenv("THIRD_MINIMAX_MODEL", ""),
        minimax_timeout_seconds=_read_int("THIRD_MINIMAX_TIMEOUT_SECONDS", 60),
        minimax_max_retries=_read_int("THIRD_MINIMAX_MAX_RETRIES", 0),
        workflowagent_use_llm=_read_bool("THIRD_WORKFLOWAGENT_USE_LLM", default=False),
        workflowagent_model=os.getenv("THIRD_WORKFLOWAGENT_MODEL") or "gpt-4o-mini",
        mysql_dsn=os.getenv("THIRD_MYSQL_DSN", ""),
        redis_url=os.getenv("THIRD_REDIS_URL", "redis://localhost:6379/0"),
        workflow_queue_name=os.getenv("THIRD_WORKFLOW_QUEUE_NAME", "third:workflow:queue"),
        workflow_consumer_group=os.getenv("THIRD_WORKFLOW_CONSUMER_GROUP", "third-workflow-workers"),
        workflow_consumer_name=os.getenv("THIRD_WORKFLOW_CONSUMER_NAME", "worker-1"),
        workflow_lock_ttl_seconds=_read_int("THIRD_WORKFLOW_LOCK_TTL_SECONDS", 300),
        workflow_pending_idle_ms=_read_int("THIRD_WORKFLOW_PENDING_IDLE_MS", 60000),
        workflow_max_deliveries=_read_int("THIRD_WORKFLOW_MAX_DELIVERIES", 5),
        workflow_dead_letter_queue_name=os.getenv("THIRD_WORKFLOW_DEAD_LETTER_QUEUE_NAME", "third:workflow:dead"),
        workflow_artifact_ttl_seconds=_read_int("THIRD_WORKFLOW_ARTIFACT_TTL_SECONDS", 3600),
        workflow_idempotency_ttl_seconds=_read_int("THIRD_WORKFLOW_IDEMPOTENCY_TTL_SECONDS", 604800),
        feishu_field_cache_ttl_seconds=_read_int("THIRD_FEISHU_FIELD_CACHE_TTL_SECONDS", 1800),
        allow_in_memory_fallback=_read_bool("THIRD_ALLOW_IN_MEMORY_FALLBACK", default=True),
        debug_enabled=debug_enabled,
        workflow_debug_log=_read_bool("THIRD_WORKFLOW_DEBUG_LOG", default=debug_enabled),
        feishu_field_name_map=_read_json_map("THIRD_FEISHU_FIELD_NAME_MAP"),
    )
    return _with_private_feishu_config(config, private_metadata if private_metadata is not None else _PRIVATE_METADATA.get())


# 这个上下文管理器让单个 workflow step 使用后端下发的私有飞书配置。
@contextmanager
def private_metadata_context(private_metadata: dict[str, Any] | None):
    token = _PRIVATE_METADATA.set(private_metadata or {})
    try:
        yield
    finally:
        _PRIVATE_METADATA.reset(token)


def _with_private_feishu_config(config: ThirdServiceConfig, private_metadata: dict[str, Any] | None) -> ThirdServiceConfig:
    if not isinstance(private_metadata, dict):
        return config
    feishu = _dict_value(private_metadata.get("feishu"))
    if not feishu:
        return config
    account = _dict_value(feishu.get("account"))
    table = _dict_value(feishu.get("table"))
    has_private_account = bool(account)
    has_private_table = bool(table)

    field_name_map = table.get("field_name_map") or table.get("fieldNameMap") or {}
    if not isinstance(field_name_map, dict):
        field_name_map = {}
    account_enabled = _bool_value(account.get("enabled"), True)
    table_enabled = _bool_value(table.get("enabled"), True)
    has_table_location = bool(_text_value(table, "app_token", "appToken") and _text_value(table, "table_id", "tableId"))
    return replace(
        config,
        feishu_app_id=_text_value(account, "app_id", "appId") if has_private_account else config.feishu_app_id,
        feishu_app_secret=_text_value(account, "app_secret", "appSecret") if has_private_account else config.feishu_app_secret,
        feishu_tenant_access_token=_text_value(account, "tenant_access_token", "tenantAccessToken") if has_private_account else config.feishu_tenant_access_token,
        feishu_app_token=_text_value(table, "app_token", "appToken") if has_private_table else config.feishu_app_token,
        feishu_table_id=_text_value(table, "table_id", "tableId") if has_private_table else config.feishu_table_id,
        feishu_table_name=(
            _text_value(table, "table_name", "tableName", "display_name", "displayName") or config.feishu_table_name
            if has_private_table
            else config.feishu_table_name
        ),
        feishu_view_id=_text_value(table, "view_id", "viewId") if has_private_table else config.feishu_view_id,
        feishu_user_id_type=(
            _text_value(account, "user_id_type", "userIdType") or "open_id"
            if has_private_account
            else config.feishu_user_id_type
        ),
        feishu_use_real=account_enabled and table_enabled and has_table_location,
        feishu_field_name_map=(
            {str(key): str(value) for key, value in field_name_map.items() if key and value}
            if has_private_table
            else config.feishu_field_name_map
        ),
    )


def _dict_value(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def _text_value(source: dict[str, Any], *keys: str) -> str:
    for key in keys:
        value = source.get(key)
        if value is not None and str(value).strip():
            return str(value).strip()
    return ""


def _bool_value(value: Any, default: bool) -> bool:
    if value is None:
        return default
    if isinstance(value, bool):
        return value
    return str(value).strip().lower() in {"1", "true", "yes", "on"}


# 这个函数防止 third runtime、migration 和 seed 误连 SpringBoot 业务库。
def validate_third_mysql_dsn(mysql_dsn: str) -> str:
    if not mysql_dsn:
        return mysql_dsn
    try:
        url = make_url(mysql_dsn)
    except Exception as exc:
        raise RuntimeError("THIRD_MYSQL_DSN 不是合法的 SQLAlchemy 数据库地址。") from exc

    database_name = (url.database or "").strip()
    username = (url.username or "").strip()
    if username in THIRD_FORBIDDEN_MYSQL_USERS:
        raise RuntimeError("THIRD_MYSQL_DSN 不能使用 SpringBoot 业务库账号 backend_user。")
    if database_name in THIRD_FORBIDDEN_MYSQL_DATABASES:
        raise RuntimeError("THIRD_MYSQL_DSN 不能连接 SpringBoot 业务库 for_mygirl_app；third 只能连接 third_service 或 third_test。")
    if url.drivername.startswith("mysql") and database_name not in THIRD_ALLOWED_MYSQL_DATABASES:
        allowed = "、".join(sorted(THIRD_ALLOWED_MYSQL_DATABASES))
        raise RuntimeError(f"THIRD_MYSQL_DSN 必须连接 third 私有库：{allowed}。")
    return mysql_dsn


# 这个函数读取字段名映射配置，用于把项目语义字段转换成真实飞书列名。
def _read_json_map(name: str) -> dict[str, str]:
    raw_value = os.getenv(name, "").strip()
    if not raw_value:
        return {}
    try:
        parsed = json.loads(raw_value)
    except json.JSONDecodeError:
        return {}
    if not isinstance(parsed, dict):
        return {}
    return {str(key): str(value) for key, value in parsed.items() if key and value}


# 这个函数自动读取 third/.env 和项目根目录 .env，系统环境变量会保留最高优先级。
def _load_env_files() -> None:
    current_file = Path(__file__).resolve()
    third_dir = current_file.parents[2]
    repo_dir = current_file.parents[3]
    for env_path in (third_dir / ".env", repo_dir / ".env"):
        _load_env_file(env_path)


# 这个函数解析简单 KEY=VALUE 格式的 .env 文件；已有非空系统环境变量保持最高优先级。
def _load_env_file(env_path: Path) -> None:
    if not env_path.exists():
        return

    for raw_line in env_path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        key = key.strip()
        value = _strip_env_value(value.strip())
        if key and (key not in os.environ or os.environ.get(key, "") == ""):
            os.environ[key] = value


# 这个函数去掉 .env 值两侧的简单引号，方便填写包含特殊字符的密钥。
def _strip_env_value(value: str) -> str:
    if len(value) >= 2 and value[0] == value[-1] and value[0] in {"'", '"'}:
        return value[1:-1]
    return value


# 这个函数统一解析布尔环境变量，避免每个 Agent 自己写一套判断。
def _read_bool(name: str, default: bool) -> bool:
    raw_value = os.getenv(name)
    if raw_value is None:
        return default
    return raw_value.strip().lower() in {"1", "true", "yes", "on"}


# 这个函数统一解析整数环境变量，非法值时使用默认配置。
def _read_int(name: str, default: int) -> int:
    raw_value = os.getenv(name)
    if raw_value is None:
        return default
    try:
        return int(raw_value.strip())
    except ValueError:
        return default


def _read_csv(name: str, default: list[str]) -> list[str]:
    raw_value = os.getenv(name)
    if raw_value is None:
        return list(default)
    values = [item.strip().lower() for item in raw_value.split(",") if item.strip()]
    return values or list(default)
