"""add private workflow metadata

Revision ID: 0004_workflow_private_metadata
Revises: 0003_workflow_session_metadata
Create Date: 2026-06-24
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "0004_workflow_private_metadata"
down_revision = "0003_workflow_session_metadata"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("workflow_sessions", sa.Column("private_metadata_json", sa.JSON(), nullable=True))


def downgrade() -> None:
    op.drop_column("workflow_sessions", "private_metadata_json")
