"""把 Prompt/runagent 下的业务 Agent 提示词同步到 prompt_registry。"""

from __future__ import annotations

import argparse
from pathlib import Path
from typing import Any

from sqlalchemy import inspect
from sqlalchemy.exc import SQLAlchemyError

try:
    import yaml
except ImportError as exc:  # pragma: no cover - 依赖缺失时脚本直接失败
    raise RuntimeError("缺少 PyYAML 依赖，无法读取 runagent 提示词 YAML。") from exc

try:
    from ..agents.shared.config import load_config
    from ..storage.database import create_session_factory
    from ..storage.models import PromptRegistryModel
    from ..storage.repository import now
except ImportError:
    from agents.shared.config import load_config
    from storage.database import create_session_factory
    from storage.models import PromptRegistryModel
    from storage.repository import now


REQUIRED_FIELDS = {
    "prompt_key",
    "agent_name",
    "role_name",
    "description",
    "db_address",
    "input_schema_json",
    "output_schema_json",
    "prompt_text",
    "version",
    "enabled",
}

PROMPT_REGISTRY_COLUMNS = {
    "prompt_key",
    "agent_name",
    "role_name",
    "description",
    "db_address",
    "input_schema_json",
    "prompt_text",
    "output_schema_json",
    "metadata_json",
    "version",
    "enabled",
    "updated_at",
}


class RunAgentPromptValidationError(ValueError):
    pass


def default_prompt_dir() -> Path:
    return Path(__file__).resolve().parents[1] / "Prompt" / "runagent"


def load_runagent_prompt_files(prompt_dir: Path | None = None) -> list[dict[str, Any]]:
    resolved_dir = prompt_dir or default_prompt_dir()
    if not resolved_dir.exists():
        raise FileNotFoundError(f"runagent 提示词目录不存在：{resolved_dir}")
    prompt_files = sorted(resolved_dir.glob("*.yaml"))
    if not prompt_files:
        raise FileNotFoundError(f"runagent 提示词目录没有 YAML 文件：{resolved_dir}")
    return [_load_prompt_file(path) for path in prompt_files]


def seed_runagent_prompts(prompt_dir: Path | None = None, session_factory: Any | None = None) -> list[dict[str, str]]:
    if session_factory is None:
        config = load_config()
        if not config.mysql_dsn:
            raise RuntimeError("未配置 THIRD_MYSQL_DSN，无法把 runagent 提示词写入 MySQL。")
        session_factory = create_session_factory()

    prompts = load_runagent_prompt_files(prompt_dir)
    updated_at = now()
    rows: list[dict[str, str]] = []
    try:
        with session_factory() as session:
            _ensure_prompt_registry_schema(session)
            for prompt in prompts:
                model = PromptRegistryModel(
                    prompt_key=str(prompt["prompt_key"]),
                    agent_name=str(prompt["agent_name"]),
                    role_name=str(prompt["role_name"]),
                    description=str(prompt["description"]),
                    db_address=str(prompt["db_address"]),
                    input_schema_json=prompt["input_schema_json"],
                    prompt_text=str(prompt["prompt_text"]),
                    output_schema_json=prompt["output_schema_json"],
                    metadata_json=prompt.get("metadata_json") or {},
                    version=str(prompt["version"]),
                    enabled=bool(prompt["enabled"]),
                    updated_at=updated_at,
                )
                session.merge(model)
                rows.append(
                    {
                        "prompt_key": model.prompt_key,
                        "agent_name": model.agent_name or "",
                        "db_address": model.db_address or "",
                    }
                )
            session.commit()
    except RuntimeError:
        raise
    except SQLAlchemyError as exc:
        raise RuntimeError(f"runagent 提示词写入 MySQL 失败：{exc}") from exc
    return rows


def _load_prompt_file(path: Path) -> dict[str, Any]:
    raw = yaml.safe_load(path.read_text(encoding="utf-8"))
    if not isinstance(raw, dict):
        raise RunAgentPromptValidationError(f"{path} 内容必须是 YAML 对象。")
    _validate_prompt(raw, path)
    return raw


def _validate_prompt(prompt: dict[str, Any], path: Path) -> None:
    missing = sorted(field for field in REQUIRED_FIELDS if field not in prompt)
    if missing:
        raise RunAgentPromptValidationError(f"{path} 缺少字段：{', '.join(missing)}")
    for field in ("prompt_key", "agent_name", "role_name", "description", "db_address", "prompt_text", "version"):
        if not str(prompt.get(field) or "").strip():
            raise RunAgentPromptValidationError(f"{path} 字段 {field} 不能为空。")
    if not isinstance(prompt.get("input_schema_json"), dict):
        raise RunAgentPromptValidationError(f"{path} 字段 input_schema_json 必须是对象。")
    if not isinstance(prompt.get("output_schema_json"), dict):
        raise RunAgentPromptValidationError(f"{path} 字段 output_schema_json 必须是对象。")
    if not isinstance(prompt.get("enabled"), bool):
        raise RunAgentPromptValidationError(f"{path} 字段 enabled 必须是布尔值。")
    expected_address = f"prompt_registry.prompt_key={prompt['prompt_key']}"
    if str(prompt.get("db_address")) != expected_address:
        raise RunAgentPromptValidationError(f"{path} 字段 db_address 必须是 {expected_address}。")


def _ensure_prompt_registry_schema(session: Any) -> None:
    try:
        columns = {column["name"] for column in inspect(session.get_bind()).get_columns("prompt_registry")}
    except SQLAlchemyError as exc:
        raise RuntimeError("无法检查 prompt_registry 表结构，请确认 MySQL 可用，并已执行 Alembic migration。") from exc

    missing = sorted(PROMPT_REGISTRY_COLUMNS - columns)
    if missing:
        raise RuntimeError(
            "prompt_registry 表结构缺少 runagent 字段："
            + "、".join(missing)
            + "。请先在项目根目录执行 `alembic upgrade head`，再执行 `python -m third.scripts.seed_runagent_prompts`。"
        )


def main() -> None:
    parser = argparse.ArgumentParser(description="Seed runagent prompts into prompt_registry.")
    parser.add_argument("--prompt-dir", default=str(default_prompt_dir()), help="runagent YAML 目录。")
    args = parser.parse_args()
    rows = seed_runagent_prompts(Path(args.prompt_dir))
    for row in rows:
        print(f"seeded {row['prompt_key']} -> {row['db_address']}")


if __name__ == "__main__":
    main()
