"""crm: add lead_id and session_id to audit_log for per-lead / per-session traces.

Revision ID: 0002
Revises: 0001
Create Date: 2026-11-03

Both columns are nullable so existing rows and callers stay valid.
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0002"
down_revision: Union[str, None] = "0001"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "audit_log",
        sa.Column("lead_id", sa.Integer(), sa.ForeignKey("leads.id"), nullable=True),
    )
    op.add_column("audit_log", sa.Column("session_id", sa.String(64), nullable=True))
    op.create_index("ix_audit_log_lead_id", "audit_log", ["lead_id"])
    op.create_index("ix_audit_log_session_id", "audit_log", ["session_id"])


def downgrade() -> None:
    op.drop_index("ix_audit_log_session_id", table_name="audit_log")
    op.drop_index("ix_audit_log_lead_id", table_name="audit_log")
    op.drop_column("audit_log", "session_id")
    op.drop_column("audit_log", "lead_id")
