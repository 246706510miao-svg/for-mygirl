"""Alembic migration 环境配置。"""

from __future__ import annotations

from logging.config import fileConfig

from alembic import context
from sqlalchemy import engine_from_config, pool

from agents.shared.config import load_config, validate_third_mysql_dsn
from storage.models import Base


# 这一段读取 Alembic 配置和日志配置。
config = context.config
if config.config_file_name is not None:
    fileConfig(config.config_file_name)


# 这一段把 SQLAlchemy 模型元数据交给 Alembic 自动比较。
target_metadata = Base.metadata


# 这个函数从 THIRD_MYSQL_DSN 注入数据库 URL。
def _database_url() -> str:
    service_config = load_config()
    if not service_config.mysql_dsn:
        raise RuntimeError("运行 Alembic migration 前必须配置 THIRD_MYSQL_DSN。")
    return validate_third_mysql_dsn(service_config.mysql_dsn)


# 这个函数运行离线 migration。
def run_migrations_offline() -> None:
    context.configure(
        url=_database_url(),
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )
    with context.begin_transaction():
        context.run_migrations()


# 这个函数运行在线 migration。
def run_migrations_online() -> None:
    section = config.get_section(config.config_ini_section, {})
    section["sqlalchemy.url"] = _database_url()
    connectable = engine_from_config(section, prefix="sqlalchemy.", poolclass=pool.NullPool)
    with connectable.connect() as connection:
        context.configure(connection=connection, target_metadata=target_metadata)
        with context.begin_transaction():
            context.run_migrations()


# 这一段根据 Alembic 当前模式选择执行方式。
if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
