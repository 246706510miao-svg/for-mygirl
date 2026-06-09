"""workflow MySQL 连接和会话工厂。"""

from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager

from sqlalchemy import Engine, create_engine
from sqlalchemy.orm import Session, sessionmaker

try:
    from ..agents.shared.config import ThirdServiceConfig, load_config
except ImportError:
    from agents.shared.config import ThirdServiceConfig, load_config

from .models import Base


# 这个函数创建 SQLAlchemy Engine；真实持久化要求配置 THIRD_MYSQL_DSN。
def create_workflow_engine(config: ThirdServiceConfig | None = None) -> Engine:
    resolved_config = config or load_config()
    if not resolved_config.mysql_dsn:
        raise RuntimeError("未配置 THIRD_MYSQL_DSN，无法创建 MySQL workflow 存储。")
    return create_engine(resolved_config.mysql_dsn, pool_pre_ping=True, future=True)


# 这个函数创建 SQLAlchemy Session 工厂，Repository 会通过它获得数据库会话。
def create_session_factory(engine: Engine | None = None) -> sessionmaker[Session]:
    resolved_engine = engine or create_workflow_engine()
    return sessionmaker(bind=resolved_engine, autoflush=False, expire_on_commit=False, future=True)


# 这个上下文管理器统一提交或回滚数据库事务。
@contextmanager
def session_scope(session_factory: sessionmaker[Session]) -> Iterator[Session]:
    session = session_factory()
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


# 这个函数用于本地调试时直接创建表；生产环境优先使用 Alembic migration。
def create_all_tables(engine: Engine | None = None) -> None:
    resolved_engine = engine or create_workflow_engine()
    Base.metadata.create_all(resolved_engine)
