"""crm: indexes for the filters the staff screens use.

Revision ID: 0006
Revises: 0005
Create Date: 2026-11-05
"""
from typing import Sequence, Union

from alembic import op

revision: str = "0006"
down_revision: Union[str, None] = "0005"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_index("ix_approvals_status", "approvals", ["status"])
    op.create_index("ix_approvals_lead_id", "approvals", ["lead_id"])
    op.create_index("ix_audit_log_event_type", "audit_log", ["event_type"])
    op.create_index("ix_leads_status", "leads", ["status"])


def downgrade() -> None:
    op.drop_index("ix_leads_status", table_name="leads")
    op.drop_index("ix_audit_log_event_type", table_name="audit_log")
    op.drop_index("ix_approvals_lead_id", table_name="approvals")
    op.drop_index("ix_approvals_status", table_name="approvals")
