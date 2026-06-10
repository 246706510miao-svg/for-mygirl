"""workflow Repository，封装 MySQL 和本地内存两种存储实现。"""

from __future__ import annotations

import hashlib
from copy import deepcopy
from datetime import datetime, timedelta
from typing import Any
from uuid import uuid4

try:
    from sqlalchemy import select
    from sqlalchemy.orm import Session, sessionmaker

    from .models import (
        FeishuFieldCacheModel,
        SessionArtifactModel,
        WorkflowConfirmationModel,
        WorkflowIdempotencyKeyModel,
        WorkflowPlanModel,
        WorkflowSessionModel,
        WorkflowStepModel,
    )
except ImportError:
    select = None
    Session = Any
    sessionmaker = Any
    FeishuFieldCacheModel = Any
    SessionArtifactModel = Any
    WorkflowConfirmationModel = Any
    WorkflowIdempotencyKeyModel = Any
    WorkflowPlanModel = Any
    WorkflowSessionModel = Any
    WorkflowStepModel = Any


# 这个函数生成 workflow 使用的短 ID，便于日志和 LangSmith 里阅读。
def new_id(prefix: str) -> str:
    return f"{prefix}_{uuid4().hex[:24]}"


# 这个函数返回当前时间，所有状态更新时间统一走这里。
def now() -> datetime:
    return datetime.utcnow()


# 这个基类定义 workflow runtime 需要的 Repository 能力。
class WorkflowRepository:
    # 这个方法创建 workflow session。
    def create_session(self, original_input: str, session_id: str | None = None, status: str = "queued") -> dict[str, Any]:
        raise NotImplementedError

    # 这个方法读取 workflow session。
    def get_session(self, session_id: str) -> dict[str, Any] | None:
        raise NotImplementedError

    # 这个方法更新 workflow session 的状态字段。
    def update_session(self, session_id: str, **fields: Any) -> dict[str, Any]:
        raise NotImplementedError

    # 这个方法保存 workflowagent 生成的计划和步骤。
    def save_plan(self, session_id: str, plan: dict[str, Any]) -> dict[str, Any]:
        raise NotImplementedError

    # 这个方法读取 session 最新计划。
    def get_plan(self, session_id: str) -> dict[str, Any] | None:
        raise NotImplementedError

    # 这个方法列出计划步骤。
    def list_steps(self, plan_id: str) -> list[dict[str, Any]]:
        raise NotImplementedError

    # 这个方法读取单个步骤。
    def get_step(self, step_id: str) -> dict[str, Any] | None:
        raise NotImplementedError

    # 这个方法更新步骤状态。
    def update_step(self, step_id: str, **fields: Any) -> dict[str, Any]:
        raise NotImplementedError

    # 这个方法保存步骤产物。
    def save_artifact(
        self,
        session_id: str,
        artifact_key: str,
        source_step_id: str | None,
        content_text: str = "",
        data_json: dict[str, Any] | None = None,
        schema_json: dict[str, Any] | None = None,
        expires_at: datetime | None = None,
    ) -> dict[str, Any]:
        raise NotImplementedError

    # 这个方法读取指定 key 的最新 artifact。
    def get_artifact(self, session_id: str, artifact_key: str) -> dict[str, Any] | None:
        raise NotImplementedError

    # 这个方法列出 session 下所有 artifact。
    def list_artifacts(self, session_id: str) -> list[dict[str, Any]]:
        raise NotImplementedError

    # 这个方法创建用户确认请求。
    def create_confirmation(
        self,
        session_id: str,
        step_id: str,
        request_text: str,
        preview_json: dict[str, Any],
        expires_at: datetime | None = None,
    ) -> dict[str, Any]:
        raise NotImplementedError

    # 这个方法读取等待中的确认请求。
    def get_waiting_confirmation(self, session_id: str) -> dict[str, Any] | None:
        raise NotImplementedError

    # 这个方法保存用户确认或拒绝结果。
    def resolve_confirmation(self, confirmation_id: str, approved: bool, user_response: str) -> dict[str, Any]:
        raise NotImplementedError

    # 这个方法读取幂等记录。
    def get_idempotency_key(self, idempotency_key: str) -> dict[str, Any] | None:
        raise NotImplementedError

    # 这个方法写入或更新幂等记录。
    def save_idempotency_key(
        self,
        idempotency_key: str,
        session_id: str,
        operation_type: str,
        target_service: str,
        payload_hash: str,
        status: str,
        result_artifact_id: str | None = None,
        expires_at: datetime | None = None,
    ) -> dict[str, Any]:
        raise NotImplementedError

    # 这个方法读取未过期的飞书字段缓存。
    def get_feishu_field_cache(self, app_token_hash: str, table_id: str, view_id: str | None) -> list[dict[str, Any]]:
        raise NotImplementedError

    # 这个方法替换飞书字段缓存。
    def replace_feishu_field_cache(
        self,
        app_token_hash: str,
        table_id: str,
        view_id: str | None,
        fields: list[dict[str, Any]],
        ttl_seconds: int,
    ) -> list[dict[str, Any]]:
        raise NotImplementedError


# 这个类使用 SQLAlchemy 操作 MySQL workflow 表。
class SqlAlchemyWorkflowRepository(WorkflowRepository):
    # 这个构造函数注入 SQLAlchemy Session 工厂。
    def __init__(self, session_factory: sessionmaker[Session]) -> None:
        if select is None:
            raise RuntimeError("缺少 SQLAlchemy 依赖，无法使用 MySQL workflow 存储。")
        self._session_factory = session_factory

    # 这个方法创建 workflow session。
    def create_session(self, original_input: str, session_id: str | None = None, status: str = "queued") -> dict[str, Any]:
        created_at = now()
        model = WorkflowSessionModel(
            session_id=session_id or new_id("sess"),
            original_input=original_input,
            status=status,
            current_step_id=None,
            final_answer=None,
            error_text=None,
            created_at=created_at,
            updated_at=created_at,
        )
        with self._session_factory() as session:
            session.add(model)
            session.commit()
            return _session_to_dict(model)

    # 这个方法读取 workflow session。
    def get_session(self, session_id: str) -> dict[str, Any] | None:
        with self._session_factory() as session:
            model = session.get(WorkflowSessionModel, session_id)
            return _session_to_dict(model) if model else None

    # 这个方法更新 workflow session。
    def update_session(self, session_id: str, **fields: Any) -> dict[str, Any]:
        with self._session_factory() as session:
            model = session.get(WorkflowSessionModel, session_id)
            if not model:
                raise KeyError(f"workflow session 不存在：{session_id}")
            for key, value in fields.items():
                if hasattr(model, key):
                    setattr(model, key, value)
            model.updated_at = now()
            session.commit()
            return _session_to_dict(model)

    # 这个方法保存 workflow plan 和 steps。
    def save_plan(self, session_id: str, plan: dict[str, Any]) -> dict[str, Any]:
        created_at = now()
        plan_id = new_id("plan")
        plan_model = WorkflowPlanModel(
            plan_id=plan_id,
            session_id=session_id,
            plan_version=str(plan.get("version") or "workflow.v1"),
            intent=str(plan.get("intent") or "unknown"),
            risk_level=str(plan.get("risk_level") or "read"),
            requires_confirmation=bool(plan.get("requires_confirmation")),
            plan_json=deepcopy(plan),
            status="planned",
            created_at=created_at,
            updated_at=created_at,
        )
        step_models = [_step_model_from_plan_step(plan_id, index, step) for index, step in enumerate(plan.get("steps") or [], start=1)]
        with self._session_factory() as session:
            session.add(plan_model)
            session.add_all(step_models)
            session.commit()
            return _plan_to_dict(plan_model)

    # 这个方法读取 session 最新计划。
    def get_plan(self, session_id: str) -> dict[str, Any] | None:
        with self._session_factory() as session:
            stmt = select(WorkflowPlanModel).where(WorkflowPlanModel.session_id == session_id).order_by(WorkflowPlanModel.created_at.desc())
            model = session.execute(stmt).scalars().first()
            return _plan_to_dict(model) if model else None

    # 这个方法列出计划步骤。
    def list_steps(self, plan_id: str) -> list[dict[str, Any]]:
        with self._session_factory() as session:
            stmt = select(WorkflowStepModel).where(WorkflowStepModel.plan_id == plan_id).order_by(WorkflowStepModel.step_seq.asc())
            return [_step_to_dict(model) for model in session.execute(stmt).scalars().all()]

    # 这个方法读取单个步骤。
    def get_step(self, step_id: str) -> dict[str, Any] | None:
        with self._session_factory() as session:
            model = session.get(WorkflowStepModel, step_id)
            return _step_to_dict(model) if model else None

    # 这个方法更新步骤状态。
    def update_step(self, step_id: str, **fields: Any) -> dict[str, Any]:
        with self._session_factory() as session:
            model = session.get(WorkflowStepModel, step_id)
            if not model:
                raise KeyError(f"workflow step 不存在：{step_id}")
            for key, value in fields.items():
                if hasattr(model, key):
                    setattr(model, key, value)
            session.commit()
            return _step_to_dict(model)

    # 这个方法保存 artifact。
    def save_artifact(
        self,
        session_id: str,
        artifact_key: str,
        source_step_id: str | None,
        content_text: str = "",
        data_json: dict[str, Any] | None = None,
        schema_json: dict[str, Any] | None = None,
        expires_at: datetime | None = None,
    ) -> dict[str, Any]:
        model = SessionArtifactModel(
            artifact_id=new_id("art"),
            session_id=session_id,
            source_step_id=source_step_id,
            artifact_key=artifact_key,
            content_text=content_text,
            data_json=deepcopy(data_json or {}),
            schema_json=deepcopy(schema_json or {}),
            expires_at=expires_at,
            created_at=now(),
        )
        with self._session_factory() as session:
            session.add(model)
            session.commit()
            return _artifact_to_dict(model)

    # 这个方法读取指定 artifact。
    def get_artifact(self, session_id: str, artifact_key: str) -> dict[str, Any] | None:
        with self._session_factory() as session:
            stmt = (
                select(SessionArtifactModel)
                .where(SessionArtifactModel.session_id == session_id, SessionArtifactModel.artifact_key == artifact_key)
                .order_by(SessionArtifactModel.created_at.desc())
            )
            model = session.execute(stmt).scalars().first()
            return _artifact_to_dict(model) if model else None

    # 这个方法列出 session artifact。
    def list_artifacts(self, session_id: str) -> list[dict[str, Any]]:
        with self._session_factory() as session:
            stmt = select(SessionArtifactModel).where(SessionArtifactModel.session_id == session_id).order_by(SessionArtifactModel.created_at.asc())
            return [_artifact_to_dict(model) for model in session.execute(stmt).scalars().all()]

    # 这个方法创建用户确认请求。
    def create_confirmation(
        self,
        session_id: str,
        step_id: str,
        request_text: str,
        preview_json: dict[str, Any],
        expires_at: datetime | None = None,
    ) -> dict[str, Any]:
        model = WorkflowConfirmationModel(
            confirmation_id=new_id("confirm"),
            session_id=session_id,
            step_id=step_id,
            status="waiting",
            request_text=request_text,
            preview_json=deepcopy(preview_json),
            user_response=None,
            expires_at=expires_at,
            decided_at=None,
            created_at=now(),
        )
        with self._session_factory() as session:
            session.add(model)
            session.commit()
            return _confirmation_to_dict(model)

    # 这个方法读取等待中的确认请求。
    def get_waiting_confirmation(self, session_id: str) -> dict[str, Any] | None:
        with self._session_factory() as session:
            stmt = (
                select(WorkflowConfirmationModel)
                .where(WorkflowConfirmationModel.session_id == session_id, WorkflowConfirmationModel.status == "waiting")
                .order_by(WorkflowConfirmationModel.created_at.desc())
            )
            model = session.execute(stmt).scalars().first()
            return _confirmation_to_dict(model) if model else None

    # 这个方法保存用户确认结果。
    def resolve_confirmation(self, confirmation_id: str, approved: bool, user_response: str) -> dict[str, Any]:
        with self._session_factory() as session:
            model = session.get(WorkflowConfirmationModel, confirmation_id)
            if not model:
                raise KeyError(f"confirmation 不存在：{confirmation_id}")
            model.status = "approved" if approved else "rejected"
            model.user_response = user_response
            model.decided_at = now()
            session.commit()
            return _confirmation_to_dict(model)

    # 这个方法读取幂等记录。
    def get_idempotency_key(self, idempotency_key: str) -> dict[str, Any] | None:
        with self._session_factory() as session:
            model = session.get(WorkflowIdempotencyKeyModel, idempotency_key)
            return _idempotency_to_dict(model) if model else None

    # 这个方法写入或更新幂等记录。
    def save_idempotency_key(
        self,
        idempotency_key: str,
        session_id: str,
        operation_type: str,
        target_service: str,
        payload_hash: str,
        status: str,
        result_artifact_id: str | None = None,
        expires_at: datetime | None = None,
    ) -> dict[str, Any]:
        with self._session_factory() as session:
            model = session.get(WorkflowIdempotencyKeyModel, idempotency_key)
            if model:
                model.status = status
                model.result_artifact_id = result_artifact_id
                model.expires_at = expires_at
            else:
                model = WorkflowIdempotencyKeyModel(
                    idempotency_key=idempotency_key,
                    session_id=session_id,
                    operation_type=operation_type,
                    target_service=target_service,
                    payload_hash=payload_hash,
                    status=status,
                    result_artifact_id=result_artifact_id,
                    expires_at=expires_at,
                    created_at=now(),
                )
                session.add(model)
            session.commit()
            return _idempotency_to_dict(model)

    # 这个方法读取未过期字段缓存。
    def get_feishu_field_cache(self, app_token_hash: str, table_id: str, view_id: str | None) -> list[dict[str, Any]]:
        with self._session_factory() as session:
            stmt = select(FeishuFieldCacheModel).where(
                FeishuFieldCacheModel.app_token_hash == app_token_hash,
                FeishuFieldCacheModel.table_id == table_id,
                FeishuFieldCacheModel.view_id == view_id,
                FeishuFieldCacheModel.expires_at > now(),
            )
            return [_field_cache_to_dict(model) for model in session.execute(stmt).scalars().all()]

    # 这个方法替换字段缓存。
    def replace_feishu_field_cache(
        self,
        app_token_hash: str,
        table_id: str,
        view_id: str | None,
        fields: list[dict[str, Any]],
        ttl_seconds: int,
    ) -> list[dict[str, Any]]:
        cached_at = now()
        expires_at = cached_at + timedelta(seconds=ttl_seconds)
        with self._session_factory() as session:
            delete_stmt = select(FeishuFieldCacheModel).where(
                FeishuFieldCacheModel.app_token_hash == app_token_hash,
                FeishuFieldCacheModel.table_id == table_id,
                FeishuFieldCacheModel.view_id == view_id,
            )
            for existing in session.execute(delete_stmt).scalars().all():
                session.delete(existing)
            models = [
                FeishuFieldCacheModel(
                    cache_id=new_id("field"),
                    app_token_hash=app_token_hash,
                    table_id=table_id,
                    view_id=view_id,
                    field_id=str(field.get("field_id") or ""),
                    field_name=str(field.get("field_name") or ""),
                    field_type=str(field.get("type") or field.get("field_type") or ""),
                    property_json=deepcopy(field.get("property") or {}),
                    writable=bool(field.get("writable", True)),
                    readonly_reason=field.get("readonly_reason"),
                    cached_at=cached_at,
                    expires_at=expires_at,
                )
                for field in fields
            ]
            session.add_all(models)
            session.commit()
            return [_field_cache_to_dict(model) for model in models]


# 这个类提供无 MySQL 时的本地内存存储，主要用于 mock 调试和 compile 后快速验证。
class InMemoryWorkflowRepository(WorkflowRepository):
    # 这个构造函数初始化所有内存表。
    def __init__(self) -> None:
        self.sessions: dict[str, dict[str, Any]] = {}
        self.plans: dict[str, dict[str, Any]] = {}
        self.steps: dict[str, dict[str, Any]] = {}
        self.artifacts: dict[str, dict[str, Any]] = {}
        self.confirmations: dict[str, dict[str, Any]] = {}
        self.idempotency_keys: dict[str, dict[str, Any]] = {}
        self.field_cache: dict[str, list[dict[str, Any]]] = {}

    # 这个方法创建 workflow session。
    def create_session(self, original_input: str, session_id: str | None = None, status: str = "queued") -> dict[str, Any]:
        created_at = now()
        row = {
            "session_id": session_id or new_id("sess"),
            "original_input": original_input,
            "status": status,
            "current_step_id": None,
            "final_answer": None,
            "error_text": None,
            "created_at": created_at,
            "updated_at": created_at,
        }
        self.sessions[row["session_id"]] = row
        return deepcopy(row)

    # 这个方法读取 workflow session。
    def get_session(self, session_id: str) -> dict[str, Any] | None:
        row = self.sessions.get(session_id)
        return deepcopy(row) if row else None

    # 这个方法更新 workflow session。
    def update_session(self, session_id: str, **fields: Any) -> dict[str, Any]:
        row = self.sessions[session_id]
        row.update({key: value for key, value in fields.items() if key in row or key in {"status", "current_step_id", "final_answer", "error_text"}})
        row["updated_at"] = now()
        return deepcopy(row)

    # 这个方法保存计划和步骤。
    def save_plan(self, session_id: str, plan: dict[str, Any]) -> dict[str, Any]:
        created_at = now()
        plan_id = new_id("plan")
        row = {
            "plan_id": plan_id,
            "session_id": session_id,
            "plan_version": str(plan.get("version") or "workflow.v1"),
            "intent": str(plan.get("intent") or "unknown"),
            "risk_level": str(plan.get("risk_level") or "read"),
            "requires_confirmation": bool(plan.get("requires_confirmation")),
            "plan_json": deepcopy(plan),
            "status": "planned",
            "created_at": created_at,
            "updated_at": created_at,
        }
        self.plans[plan_id] = row
        for index, step in enumerate(plan.get("steps") or [], start=1):
            step_row = _step_dict_from_plan_step(plan_id, index, step)
            self.steps[step_row["step_id"]] = step_row
        return deepcopy(row)

    # 这个方法读取 session 最新计划。
    def get_plan(self, session_id: str) -> dict[str, Any] | None:
        rows = [row for row in self.plans.values() if row["session_id"] == session_id]
        rows.sort(key=lambda item: item["created_at"], reverse=True)
        return deepcopy(rows[0]) if rows else None

    # 这个方法列出计划步骤。
    def list_steps(self, plan_id: str) -> list[dict[str, Any]]:
        rows = [row for row in self.steps.values() if row["plan_id"] == plan_id]
        rows.sort(key=lambda item: item["step_seq"])
        return deepcopy(rows)

    # 这个方法读取单个步骤。
    def get_step(self, step_id: str) -> dict[str, Any] | None:
        row = self.steps.get(step_id)
        return deepcopy(row) if row else None

    # 这个方法更新步骤状态。
    def update_step(self, step_id: str, **fields: Any) -> dict[str, Any]:
        row = self.steps[step_id]
        row.update(fields)
        return deepcopy(row)

    # 这个方法保存 artifact。
    def save_artifact(
        self,
        session_id: str,
        artifact_key: str,
        source_step_id: str | None,
        content_text: str = "",
        data_json: dict[str, Any] | None = None,
        schema_json: dict[str, Any] | None = None,
        expires_at: datetime | None = None,
    ) -> dict[str, Any]:
        row = {
            "artifact_id": new_id("art"),
            "session_id": session_id,
            "source_step_id": source_step_id,
            "artifact_key": artifact_key,
            "content_text": content_text,
            "data_json": deepcopy(data_json or {}),
            "schema_json": deepcopy(schema_json or {}),
            "expires_at": expires_at,
            "created_at": now(),
        }
        self.artifacts[row["artifact_id"]] = row
        return deepcopy(row)

    # 这个方法读取 artifact。
    def get_artifact(self, session_id: str, artifact_key: str) -> dict[str, Any] | None:
        rows = [row for row in self.artifacts.values() if row["session_id"] == session_id and row["artifact_key"] == artifact_key]
        rows.sort(key=lambda item: item["created_at"], reverse=True)
        return deepcopy(rows[0]) if rows else None

    # 这个方法列出 session artifact。
    def list_artifacts(self, session_id: str) -> list[dict[str, Any]]:
        rows = [row for row in self.artifacts.values() if row["session_id"] == session_id]
        rows.sort(key=lambda item: item["created_at"])
        return deepcopy(rows)

    # 这个方法创建确认请求。
    def create_confirmation(
        self,
        session_id: str,
        step_id: str,
        request_text: str,
        preview_json: dict[str, Any],
        expires_at: datetime | None = None,
    ) -> dict[str, Any]:
        row = {
            "confirmation_id": new_id("confirm"),
            "session_id": session_id,
            "step_id": step_id,
            "status": "waiting",
            "request_text": request_text,
            "preview_json": deepcopy(preview_json),
            "user_response": None,
            "expires_at": expires_at,
            "decided_at": None,
            "created_at": now(),
        }
        self.confirmations[row["confirmation_id"]] = row
        return deepcopy(row)

    # 这个方法读取等待中的确认。
    def get_waiting_confirmation(self, session_id: str) -> dict[str, Any] | None:
        rows = [row for row in self.confirmations.values() if row["session_id"] == session_id and row["status"] == "waiting"]
        rows.sort(key=lambda item: item["created_at"], reverse=True)
        return deepcopy(rows[0]) if rows else None

    # 这个方法保存确认结果。
    def resolve_confirmation(self, confirmation_id: str, approved: bool, user_response: str) -> dict[str, Any]:
        row = self.confirmations[confirmation_id]
        row["status"] = "approved" if approved else "rejected"
        row["user_response"] = user_response
        row["decided_at"] = now()
        return deepcopy(row)

    # 这个方法读取幂等记录。
    def get_idempotency_key(self, idempotency_key: str) -> dict[str, Any] | None:
        row = self.idempotency_keys.get(idempotency_key)
        return deepcopy(row) if row else None

    # 这个方法写入幂等记录。
    def save_idempotency_key(
        self,
        idempotency_key: str,
        session_id: str,
        operation_type: str,
        target_service: str,
        payload_hash: str,
        status: str,
        result_artifact_id: str | None = None,
        expires_at: datetime | None = None,
    ) -> dict[str, Any]:
        row = {
            "idempotency_key": idempotency_key,
            "session_id": session_id,
            "operation_type": operation_type,
            "target_service": target_service,
            "payload_hash": payload_hash,
            "status": status,
            "result_artifact_id": result_artifact_id,
            "expires_at": expires_at,
            "created_at": self.idempotency_keys.get(idempotency_key, {}).get("created_at", now()),
        }
        self.idempotency_keys[idempotency_key] = row
        return deepcopy(row)

    # 这个方法读取未过期字段缓存。
    def get_feishu_field_cache(self, app_token_hash: str, table_id: str, view_id: str | None) -> list[dict[str, Any]]:
        rows = self.field_cache.get(_field_cache_key(app_token_hash, table_id, view_id), [])
        current_time = now()
        return deepcopy([row for row in rows if row.get("expires_at") and row["expires_at"] > current_time])

    # 这个方法替换字段缓存。
    def replace_feishu_field_cache(
        self,
        app_token_hash: str,
        table_id: str,
        view_id: str | None,
        fields: list[dict[str, Any]],
        ttl_seconds: int,
    ) -> list[dict[str, Any]]:
        cached_at = now()
        expires_at = cached_at + timedelta(seconds=ttl_seconds)
        rows = [
            {
                "cache_id": new_id("field"),
                "app_token_hash": app_token_hash,
                "table_id": table_id,
                "view_id": view_id,
                "field_id": str(field.get("field_id") or ""),
                "field_name": str(field.get("field_name") or ""),
                "field_type": str(field.get("type") or field.get("field_type") or ""),
                "property_json": deepcopy(field.get("property") or {}),
                "writable": bool(field.get("writable", True)),
                "readonly_reason": field.get("readonly_reason"),
                "cached_at": cached_at,
                "expires_at": expires_at,
            }
            for field in fields
        ]
        self.field_cache[_field_cache_key(app_token_hash, table_id, view_id)] = rows
        return deepcopy(rows)


# 这个函数把计划步骤转换成 SQLAlchemy 模型。
def _step_model_from_plan_step(plan_id: str, index: int, step: dict[str, Any]) -> WorkflowStepModel:
    row = _step_dict_from_plan_step(plan_id, index, step)
    return WorkflowStepModel(**row)


# 这个函数把计划步骤转换成通用字典。
def _step_dict_from_plan_step(plan_id: str, index: int, step: dict[str, Any]) -> dict[str, Any]:
    local_step_id = _local_step_id(index, step)
    return {
        "step_id": _database_step_id(plan_id, local_step_id, index),
        "local_step_id": local_step_id,
        "plan_id": plan_id,
        "step_seq": index,
        "kind": str(step.get("kind") or ""),
        "tool_name": step.get("tool_name"),
        "agent_name": step.get("agent_name"),
        "prompt_ref": step.get("prompt_ref"),
        "input_spec_json": deepcopy(step.get("input") or step.get("input_spec") or {}),
        "output_key": step.get("output", {}).get("save_as") if isinstance(step.get("output"), dict) else step.get("output_key"),
        "validation_json": deepcopy(step.get("validation") or {}),
        "status": "pending",
        "attempt_count": 0,
        "error_text": None,
        "started_at": None,
        "finished_at": None,
    }


# 这个函数保留 workflow_plan 内的本地步骤 ID，便于阅读和调试。
def _local_step_id(index: int, step: dict[str, Any]) -> str:
    value = str(step.get("step_id") or f"step_{index}").strip()
    return value or f"step_{index}"


# 这个函数生成数据库全局唯一步骤 ID，避免不同 session 的固定步骤名冲突。
def _database_step_id(plan_id: str, local_step_id: str, index: int) -> str:
    candidate = f"{plan_id}_{local_step_id}"
    if len(candidate) <= 64:
        return candidate
    digest = hashlib.sha1(candidate.encode("utf-8")).hexdigest()[:16]
    return f"{plan_id}_s{index}_{digest}"[:64]


# 这个函数把 session 模型转换成字典。
def _session_to_dict(model: WorkflowSessionModel) -> dict[str, Any]:
    return {
        "session_id": model.session_id,
        "original_input": model.original_input,
        "status": model.status,
        "current_step_id": model.current_step_id,
        "final_answer": model.final_answer,
        "error_text": model.error_text,
        "created_at": model.created_at,
        "updated_at": model.updated_at,
    }


# 这个函数把 plan 模型转换成字典。
def _plan_to_dict(model: WorkflowPlanModel) -> dict[str, Any]:
    return {
        "plan_id": model.plan_id,
        "session_id": model.session_id,
        "plan_version": model.plan_version,
        "intent": model.intent,
        "risk_level": model.risk_level,
        "requires_confirmation": model.requires_confirmation,
        "plan_json": model.plan_json,
        "status": model.status,
        "created_at": model.created_at,
        "updated_at": model.updated_at,
    }


# 这个函数把 step 模型转换成字典。
def _step_to_dict(model: WorkflowStepModel) -> dict[str, Any]:
    return {
        "step_id": model.step_id,
        "local_step_id": model.local_step_id,
        "plan_id": model.plan_id,
        "step_seq": model.step_seq,
        "kind": model.kind,
        "tool_name": model.tool_name,
        "agent_name": model.agent_name,
        "prompt_ref": model.prompt_ref,
        "input_spec_json": model.input_spec_json,
        "output_key": model.output_key,
        "validation_json": model.validation_json,
        "status": model.status,
        "attempt_count": model.attempt_count,
        "error_text": model.error_text,
        "started_at": model.started_at,
        "finished_at": model.finished_at,
    }


# 这个函数把 artifact 模型转换成字典。
def _artifact_to_dict(model: SessionArtifactModel) -> dict[str, Any]:
    return {
        "artifact_id": model.artifact_id,
        "session_id": model.session_id,
        "source_step_id": model.source_step_id,
        "artifact_key": model.artifact_key,
        "content_text": model.content_text,
        "data_json": model.data_json,
        "schema_json": model.schema_json,
        "expires_at": model.expires_at,
        "created_at": model.created_at,
    }


# 这个函数把 confirmation 模型转换成字典。
def _confirmation_to_dict(model: WorkflowConfirmationModel) -> dict[str, Any]:
    return {
        "confirmation_id": model.confirmation_id,
        "session_id": model.session_id,
        "step_id": model.step_id,
        "status": model.status,
        "request_text": model.request_text,
        "preview_json": model.preview_json,
        "user_response": model.user_response,
        "expires_at": model.expires_at,
        "decided_at": model.decided_at,
        "created_at": model.created_at,
    }


# 这个函数把幂等模型转换成字典。
def _idempotency_to_dict(model: WorkflowIdempotencyKeyModel) -> dict[str, Any]:
    return {
        "idempotency_key": model.idempotency_key,
        "session_id": model.session_id,
        "operation_type": model.operation_type,
        "target_service": model.target_service,
        "payload_hash": model.payload_hash,
        "status": model.status,
        "result_artifact_id": model.result_artifact_id,
        "expires_at": model.expires_at,
        "created_at": model.created_at,
    }


# 这个函数把字段缓存模型转换成字典。
def _field_cache_to_dict(model: FeishuFieldCacheModel) -> dict[str, Any]:
    return {
        "cache_id": model.cache_id,
        "app_token_hash": model.app_token_hash,
        "table_id": model.table_id,
        "view_id": model.view_id,
        "field_id": model.field_id,
        "field_name": model.field_name,
        "field_type": model.field_type,
        "property_json": model.property_json,
        "writable": model.writable,
        "readonly_reason": model.readonly_reason,
        "cached_at": model.cached_at,
        "expires_at": model.expires_at,
    }


# 这个函数生成内存字段缓存的组合 key。
def _field_cache_key(app_token_hash: str, table_id: str, view_id: str | None) -> str:
    return f"{app_token_hash}:{table_id}:{view_id or ''}"
