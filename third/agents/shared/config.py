"""第三方服务模块的环境变量配置。"""

from __future__ import annotations

import os
import json
from dataclasses import dataclass
from pathlib import Path


# 这一段定义 mock 表格的默认定位信息，用于还没有接入真实飞书时继续验证 LangGraph。
DEFAULT_APP_TOKEN = "app_mock_for_mygirl"
DEFAULT_TABLE_ID = "tbl_mock_records"
DEFAULT_TABLE_NAME = "项目记录"


# 这个数据类集中管理飞书读取和 finagent LLM 所需配置，避免配置散落在各个文件里。
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
    finagent_use_llm: bool
    finagent_model: str
    workflowagent_use_llm: bool
    workflowagent_model: str
    mysql_dsn: str
    redis_url: str
    workflow_queue_name: str
    workflow_consumer_group: str
    workflow_consumer_name: str
    workflow_lock_ttl_seconds: int
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


# 这个函数从环境变量和 .env 文件创建配置对象；你后续收集到真实信息后只需要填配置。
def load_config() -> ThirdServiceConfig:
    _load_env_files()
    debug_enabled = _read_bool("THIRD_DEBUG_ENABLED", default=True)
    return ThirdServiceConfig(
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
        finagent_use_llm=_read_bool("THIRD_FINAGENT_USE_LLM", default=False),
        finagent_model=os.getenv("THIRD_FINAGENT_MODEL") or os.getenv("THIRD_ROUTER_MODEL", "gpt-4o-mini"),
        workflowagent_use_llm=_read_bool("THIRD_WORKFLOWAGENT_USE_LLM", default=False),
        workflowagent_model=os.getenv("THIRD_WORKFLOWAGENT_MODEL") or os.getenv("THIRD_FINAGENT_MODEL") or "gpt-4o-mini",
        mysql_dsn=os.getenv("THIRD_MYSQL_DSN", ""),
        redis_url=os.getenv("THIRD_REDIS_URL", "redis://localhost:6379/0"),
        workflow_queue_name=os.getenv("THIRD_WORKFLOW_QUEUE_NAME", "third:workflow:queue"),
        workflow_consumer_group=os.getenv("THIRD_WORKFLOW_CONSUMER_GROUP", "third-workflow-workers"),
        workflow_consumer_name=os.getenv("THIRD_WORKFLOW_CONSUMER_NAME", "worker-1"),
        workflow_lock_ttl_seconds=_read_int("THIRD_WORKFLOW_LOCK_TTL_SECONDS", 300),
        workflow_artifact_ttl_seconds=_read_int("THIRD_WORKFLOW_ARTIFACT_TTL_SECONDS", 3600),
        workflow_idempotency_ttl_seconds=_read_int("THIRD_WORKFLOW_IDEMPOTENCY_TTL_SECONDS", 604800),
        feishu_field_cache_ttl_seconds=_read_int("THIRD_FEISHU_FIELD_CACHE_TTL_SECONDS", 1800),
        allow_in_memory_fallback=_read_bool("THIRD_ALLOW_IN_MEMORY_FALLBACK", default=True),
        debug_enabled=debug_enabled,
        workflow_debug_log=_read_bool("THIRD_WORKFLOW_DEBUG_LOG", default=debug_enabled),
        feishu_field_name_map=_read_json_map("THIRD_FEISHU_FIELD_NAME_MAP"),
    )


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
