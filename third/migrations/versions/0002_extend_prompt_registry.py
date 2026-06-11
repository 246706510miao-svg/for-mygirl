"""extend prompt registry for runagent catalog

Revision ID: 0002_extend_prompt_registry
Revises: 0001_workflow_tables
Create Date: 2026-06-11
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "0002_extend_prompt_registry"
down_revision = "0001_workflow_tables"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("prompt_registry", sa.Column("agent_name", sa.String(length=128), nullable=True))
    op.add_column("prompt_registry", sa.Column("description", sa.Text(), nullable=True))
    op.add_column("prompt_registry", sa.Column("db_address", sa.String(length=255), nullable=True))
    op.add_column("prompt_registry", sa.Column("input_schema_json", sa.JSON(), nullable=True))
    op.add_column("prompt_registry", sa.Column("metadata_json", sa.JSON(), nullable=True))


def downgrade() -> None:
    op.drop_column("prompt_registry", "metadata_json")
    op.drop_column("prompt_registry", "input_schema_json")
    op.drop_column("prompt_registry", "db_address")
    op.drop_column("prompt_registry", "description")
    op.drop_column("prompt_registry", "agent_name")
