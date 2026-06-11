"""workflow MySQL 表模型。"""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, JSON, String, Text, UniqueConstraint
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


# 这个基类承载 workflow 相关 SQLAlchemy 模型的元数据。
class Base(DeclarativeBase):
    pass


# 这个模型保存一次 workflow 的总状态。
class WorkflowSessionModel(Base):
    __tablename__ = "workflow_sessions"

    session_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    original_input: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[str] = mapped_column(String(32), nullable=False, index=True)
    current_step_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    final_answer: Mapped[str | None] = mapped_column(Text, nullable=True)
    error_text: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)


# 这个模型保存 workflowagent 生成的完整计划。
class WorkflowPlanModel(Base):
    __tablename__ = "workflow_plans"

    plan_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    session_id: Mapped[str] = mapped_column(String(64), ForeignKey("workflow_sessions.session_id"), nullable=False, index=True)
    plan_version: Mapped[str] = mapped_column(String(32), nullable=False)
    intent: Mapped[str] = mapped_column(String(64), nullable=False)
    risk_level: Mapped[str] = mapped_column(String(32), nullable=False)
    requires_confirmation: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    plan_json: Mapped[dict] = mapped_column(JSON, nullable=False)
    status: Mapped[str] = mapped_column(String(32), nullable=False, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)


# 这个模型保存计划中的单个可执行步骤。
class WorkflowStepModel(Base):
    __tablename__ = "workflow_steps"
    __table_args__ = (UniqueConstraint("plan_id", "local_step_id", name="uq_workflow_steps_plan_local_step_id"),)

    step_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    local_step_id: Mapped[str] = mapped_column(String(128), nullable=False)
    plan_id: Mapped[str] = mapped_column(String(64), ForeignKey("workflow_plans.plan_id"), nullable=False, index=True)
    step_seq: Mapped[int] = mapped_column(Integer, nullable=False)
    kind: Mapped[str] = mapped_column(String(32), nullable=False)
    tool_name: Mapped[str | None] = mapped_column(String(128), nullable=True)
    agent_name: Mapped[str | None] = mapped_column(String(128), nullable=True)
    prompt_ref: Mapped[str | None] = mapped_column(String(128), nullable=True)
    input_spec_json: Mapped[dict] = mapped_column(JSON, nullable=False)
    output_key: Mapped[str | None] = mapped_column(String(128), nullable=True)
    validation_json: Mapped[dict] = mapped_column(JSON, nullable=False)
    status: Mapped[str] = mapped_column(String(32), nullable=False, index=True)
    attempt_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    error_text: Mapped[str | None] = mapped_column(Text, nullable=True)
    started_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)


# 这个模型保存步骤之间传递的中间结果。
class SessionArtifactModel(Base):
    __tablename__ = "session_artifacts"

    artifact_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    session_id: Mapped[str] = mapped_column(String(64), ForeignKey("workflow_sessions.session_id"), nullable=False, index=True)
    source_step_id: Mapped[str | None] = mapped_column(String(64), ForeignKey("workflow_steps.step_id"), nullable=True)
    artifact_key: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    content_text: Mapped[str | None] = mapped_column(Text, nullable=True)
    data_json: Mapped[dict] = mapped_column(JSON, nullable=False)
    schema_json: Mapped[dict] = mapped_column(JSON, nullable=False)
    expires_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)


# 这个模型保存写入、更新、删除前的用户确认请求。
class WorkflowConfirmationModel(Base):
    __tablename__ = "workflow_confirmations"

    confirmation_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    session_id: Mapped[str] = mapped_column(String(64), ForeignKey("workflow_sessions.session_id"), nullable=False, index=True)
    step_id: Mapped[str] = mapped_column(String(64), ForeignKey("workflow_steps.step_id"), nullable=False, index=True)
    status: Mapped[str] = mapped_column(String(32), nullable=False, index=True)
    request_text: Mapped[str] = mapped_column(Text, nullable=False)
    preview_json: Mapped[dict] = mapped_column(JSON, nullable=False)
    user_response: Mapped[str | None] = mapped_column(Text, nullable=True)
    expires_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    decided_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)


# 这个模型保存写入类操作的幂等状态。
class WorkflowIdempotencyKeyModel(Base):
    __tablename__ = "workflow_idempotency_keys"

    idempotency_key: Mapped[str] = mapped_column(String(128), primary_key=True)
    session_id: Mapped[str] = mapped_column(String(64), ForeignKey("workflow_sessions.session_id"), nullable=False, index=True)
    operation_type: Mapped[str] = mapped_column(String(64), nullable=False)
    target_service: Mapped[str] = mapped_column(String(64), nullable=False)
    payload_hash: Mapped[str] = mapped_column(String(128), nullable=False)
    status: Mapped[str] = mapped_column(String(32), nullable=False, index=True)
    result_artifact_id: Mapped[str | None] = mapped_column(String(64), ForeignKey("session_artifacts.artifact_id"), nullable=True)
    expires_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)


# 这个模型保存 Agent Runner 可使用的提示词。
class PromptRegistryModel(Base):
    __tablename__ = "prompt_registry"

    prompt_key: Mapped[str] = mapped_column(String(128), primary_key=True)
    agent_name: Mapped[str | None] = mapped_column(String(128), nullable=True)
    role_name: Mapped[str] = mapped_column(String(128), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    db_address: Mapped[str | None] = mapped_column(String(255), nullable=True)
    input_schema_json: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    prompt_text: Mapped[str] = mapped_column(Text, nullable=False)
    output_schema_json: Mapped[dict] = mapped_column(JSON, nullable=False)
    metadata_json: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    version: Mapped[str] = mapped_column(String(32), nullable=False)
    enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    updated_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)


# 这个模型保存 Tool Dispatcher 可调用的工具注册信息。
class ToolRegistryModel(Base):
    __tablename__ = "tool_registry"

    tool_name: Mapped[str] = mapped_column(String(128), primary_key=True)
    category: Mapped[str] = mapped_column(String(64), nullable=False)
    input_schema_json: Mapped[dict] = mapped_column(JSON, nullable=False)
    output_schema_json: Mapped[dict] = mapped_column(JSON, nullable=False)
    side_effect_level: Mapped[str] = mapped_column(String(32), nullable=False)
    required_config_json: Mapped[dict] = mapped_column(JSON, nullable=False)
    version: Mapped[str] = mapped_column(String(32), nullable=False)
    enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    updated_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)


# 这个模型缓存飞书多维表格字段定义，用于 TTL 刷新和写入校验。
class FeishuFieldCacheModel(Base):
    __tablename__ = "feishu_field_cache"

    cache_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    app_token_hash: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    table_id: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    view_id: Mapped[str | None] = mapped_column(String(128), nullable=True)
    field_id: Mapped[str] = mapped_column(String(128), nullable=False)
    field_name: Mapped[str] = mapped_column(String(255), nullable=False)
    field_type: Mapped[str] = mapped_column(String(64), nullable=False)
    property_json: Mapped[dict] = mapped_column(JSON, nullable=False)
    writable: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    readonly_reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    cached_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    expires_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, index=True)
