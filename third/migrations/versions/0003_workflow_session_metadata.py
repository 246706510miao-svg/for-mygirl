"""add workflow session metadata

Revision ID: 0003_workflow_session_metadata
Revises: 0002_extend_prompt_registry
Create Date: 2026-06-16
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "0003_workflow_session_metadata"
down_revision = "0002_extend_prompt_registry"
branch_labels = None
depends_on = None


# 这个函数给 workflow session 增加业务侧追踪 metadata。
def upgrade() -> None:
    op.add_column("workflow_sessions", sa.Column("metadata_json", sa.JSON(), nullable=True))


# 这个函数回滚 workflow session metadata。
def downgrade() -> None:
    op.drop_column("workflow_sessions", "metadata_json")
