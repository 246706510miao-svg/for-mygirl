"""create workflow tables

Revision ID: 0001_workflow_tables
Revises:
Create Date: 2026-06-09
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa


# 这一段定义 Alembic migration 的版本号。
revision = "0001_workflow_tables"
down_revision = None
branch_labels = None
depends_on = None


# 这个函数创建 workflow 运行需要的全部 MySQL 表。
def upgrade() -> None:
    op.create_table(
        "workflow_sessions",
        sa.Column("session_id", sa.String(length=64), primary_key=True),
        sa.Column("original_input", sa.Text(), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("current_step_id", sa.String(length=64), nullable=True),
        sa.Column("final_answer", sa.Text(), nullable=True),
        sa.Column("error_text", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
    )
    op.create_index("ix_workflow_sessions_status", "workflow_sessions", ["status"])

    op.create_table(
        "workflow_plans",
        sa.Column("plan_id", sa.String(length=64), primary_key=True),
        sa.Column("session_id", sa.String(length=64), sa.ForeignKey("workflow_sessions.session_id"), nullable=False),
        sa.Column("plan_version", sa.String(length=32), nullable=False),
        sa.Column("intent", sa.String(length=64), nullable=False),
        sa.Column("risk_level", sa.String(length=32), nullable=False),
        sa.Column("requires_confirmation", sa.Boolean(), nullable=False),
        sa.Column("plan_json", sa.JSON(), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
    )
    op.create_index("ix_workflow_plans_session_id", "workflow_plans", ["session_id"])
    op.create_index("ix_workflow_plans_status", "workflow_plans", ["status"])

    op.create_table(
        "workflow_steps",
        sa.Column("step_id", sa.String(length=64), primary_key=True),
        sa.Column("plan_id", sa.String(length=64), sa.ForeignKey("workflow_plans.plan_id"), nullable=False),
        sa.Column("step_seq", sa.Integer(), nullable=False),
        sa.Column("kind", sa.String(length=32), nullable=False),
        sa.Column("tool_name", sa.String(length=128), nullable=True),
        sa.Column("agent_name", sa.String(length=128), nullable=True),
        sa.Column("prompt_ref", sa.String(length=128), nullable=True),
        sa.Column("input_spec_json", sa.JSON(), nullable=False),
        sa.Column("output_key", sa.String(length=128), nullable=True),
        sa.Column("validation_json", sa.JSON(), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("attempt_count", sa.Integer(), nullable=False),
        sa.Column("error_text", sa.Text(), nullable=True),
        sa.Column("started_at", sa.DateTime(), nullable=True),
        sa.Column("finished_at", sa.DateTime(), nullable=True),
    )
    op.create_index("ix_workflow_steps_plan_id", "workflow_steps", ["plan_id"])
    op.create_index("ix_workflow_steps_status", "workflow_steps", ["status"])

    op.create_table(
        "session_artifacts",
        sa.Column("artifact_id", sa.String(length=64), primary_key=True),
        sa.Column("session_id", sa.String(length=64), sa.ForeignKey("workflow_sessions.session_id"), nullable=False),
        sa.Column("source_step_id", sa.String(length=64), sa.ForeignKey("workflow_steps.step_id"), nullable=True),
        sa.Column("artifact_key", sa.String(length=128), nullable=False),
        sa.Column("content_text", sa.Text(), nullable=True),
        sa.Column("data_json", sa.JSON(), nullable=False),
        sa.Column("schema_json", sa.JSON(), nullable=False),
        sa.Column("expires_at", sa.DateTime(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
    )
    op.create_index("ix_session_artifacts_session_id", "session_artifacts", ["session_id"])
    op.create_index("ix_session_artifacts_artifact_key", "session_artifacts", ["artifact_key"])

    op.create_table(
        "workflow_confirmations",
        sa.Column("confirmation_id", sa.String(length=64), primary_key=True),
        sa.Column("session_id", sa.String(length=64), sa.ForeignKey("workflow_sessions.session_id"), nullable=False),
        sa.Column("step_id", sa.String(length=64), sa.ForeignKey("workflow_steps.step_id"), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("request_text", sa.Text(), nullable=False),
        sa.Column("preview_json", sa.JSON(), nullable=False),
        sa.Column("user_response", sa.Text(), nullable=True),
        sa.Column("expires_at", sa.DateTime(), nullable=True),
        sa.Column("decided_at", sa.DateTime(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
    )
    op.create_index("ix_workflow_confirmations_session_id", "workflow_confirmations", ["session_id"])
    op.create_index("ix_workflow_confirmations_step_id", "workflow_confirmations", ["step_id"])
    op.create_index("ix_workflow_confirmations_status", "workflow_confirmations", ["status"])

    op.create_table(
        "workflow_idempotency_keys",
        sa.Column("idempotency_key", sa.String(length=128), primary_key=True),
        sa.Column("session_id", sa.String(length=64), sa.ForeignKey("workflow_sessions.session_id"), nullable=False),
        sa.Column("operation_type", sa.String(length=64), nullable=False),
        sa.Column("target_service", sa.String(length=64), nullable=False),
        sa.Column("payload_hash", sa.String(length=128), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("result_artifact_id", sa.String(length=64), sa.ForeignKey("session_artifacts.artifact_id"), nullable=True),
        sa.Column("expires_at", sa.DateTime(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
    )
    op.create_index("ix_workflow_idempotency_keys_session_id", "workflow_idempotency_keys", ["session_id"])
    op.create_index("ix_workflow_idempotency_keys_status", "workflow_idempotency_keys", ["status"])

    op.create_table(
        "prompt_registry",
        sa.Column("prompt_key", sa.String(length=128), primary_key=True),
        sa.Column("role_name", sa.String(length=128), nullable=False),
        sa.Column("prompt_text", sa.Text(), nullable=False),
        sa.Column("output_schema_json", sa.JSON(), nullable=False),
        sa.Column("version", sa.String(length=32), nullable=False),
        sa.Column("enabled", sa.Boolean(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
    )

    op.create_table(
        "tool_registry",
        sa.Column("tool_name", sa.String(length=128), primary_key=True),
        sa.Column("category", sa.String(length=64), nullable=False),
        sa.Column("input_schema_json", sa.JSON(), nullable=False),
        sa.Column("output_schema_json", sa.JSON(), nullable=False),
        sa.Column("side_effect_level", sa.String(length=32), nullable=False),
        sa.Column("required_config_json", sa.JSON(), nullable=False),
        sa.Column("version", sa.String(length=32), nullable=False),
        sa.Column("enabled", sa.Boolean(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
    )

    op.create_table(
        "feishu_field_cache",
        sa.Column("cache_id", sa.String(length=64), primary_key=True),
        sa.Column("app_token_hash", sa.String(length=128), nullable=False),
        sa.Column("table_id", sa.String(length=128), nullable=False),
        sa.Column("view_id", sa.String(length=128), nullable=True),
        sa.Column("field_id", sa.String(length=128), nullable=False),
        sa.Column("field_name", sa.String(length=255), nullable=False),
        sa.Column("field_type", sa.String(length=64), nullable=False),
        sa.Column("property_json", sa.JSON(), nullable=False),
        sa.Column("writable", sa.Boolean(), nullable=False),
        sa.Column("readonly_reason", sa.Text(), nullable=True),
        sa.Column("cached_at", sa.DateTime(), nullable=False),
        sa.Column("expires_at", sa.DateTime(), nullable=False),
    )
    op.create_index("ix_feishu_field_cache_app_token_hash", "feishu_field_cache", ["app_token_hash"])
    op.create_index("ix_feishu_field_cache_table_id", "feishu_field_cache", ["table_id"])
    op.create_index("ix_feishu_field_cache_expires_at", "feishu_field_cache", ["expires_at"])


# 这个函数回滚 workflow 相关表。
def downgrade() -> None:
    op.drop_index("ix_feishu_field_cache_expires_at", table_name="feishu_field_cache")
    op.drop_index("ix_feishu_field_cache_table_id", table_name="feishu_field_cache")
    op.drop_index("ix_feishu_field_cache_app_token_hash", table_name="feishu_field_cache")
    op.drop_table("feishu_field_cache")
    op.drop_table("tool_registry")
    op.drop_table("prompt_registry")
    op.drop_index("ix_workflow_idempotency_keys_status", table_name="workflow_idempotency_keys")
    op.drop_index("ix_workflow_idempotency_keys_session_id", table_name="workflow_idempotency_keys")
    op.drop_table("workflow_idempotency_keys")
    op.drop_index("ix_workflow_confirmations_status", table_name="workflow_confirmations")
    op.drop_index("ix_workflow_confirmations_step_id", table_name="workflow_confirmations")
    op.drop_index("ix_workflow_confirmations_session_id", table_name="workflow_confirmations")
    op.drop_table("workflow_confirmations")
    op.drop_index("ix_session_artifacts_artifact_key", table_name="session_artifacts")
    op.drop_index("ix_session_artifacts_session_id", table_name="session_artifacts")
    op.drop_table("session_artifacts")
    op.drop_index("ix_workflow_steps_status", table_name="workflow_steps")
    op.drop_index("ix_workflow_steps_plan_id", table_name="workflow_steps")
    op.drop_table("workflow_steps")
    op.drop_index("ix_workflow_plans_status", table_name="workflow_plans")
    op.drop_index("ix_workflow_plans_session_id", table_name="workflow_plans")
    op.drop_table("workflow_plans")
    op.drop_index("ix_workflow_sessions_status", table_name="workflow_sessions")
    op.drop_table("workflow_sessions")
