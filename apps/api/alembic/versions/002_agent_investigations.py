"""Agent investigations: each question, its event trail and evidence.

Revision ID: 002
Revises: 001
Create Date: 2026-10-22
"""
from __future__ import annotations

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB

revision = "002"
down_revision = "001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "agent_investigations",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("user_id", sa.Uuid(), sa.ForeignKey("user_profiles.id", ondelete="SET NULL"), nullable=True),
        sa.Column("question", sa.Text(), nullable=False),
        sa.Column("model_id", sa.String(32), nullable=False),
        sa.Column("model_name", sa.Text(), nullable=False),
        # running | completed | failed | refused | cancelled
        sa.Column("status", sa.String(16), nullable=False, server_default="running"),
        sa.Column("answer", sa.Text(), nullable=True),
        sa.Column("error", sa.Text(), nullable=True),
        sa.Column("events", JSONB(), nullable=False, server_default=sa.text("'[]'::jsonb")),
        sa.Column("evidence", JSONB(), nullable=False, server_default=sa.text("'[]'::jsonb")),
        sa.Column("tool_calls", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("duration_ms", sa.Integer(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index("ix_agent_investigations_user_created", "agent_investigations", ["user_id", "created_at"])


def downgrade() -> None:
    op.drop_index("ix_agent_investigations_user_created", table_name="agent_investigations")
    op.drop_table("agent_investigations")
