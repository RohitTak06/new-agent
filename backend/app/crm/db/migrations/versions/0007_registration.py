"""crm: student self-registration. A lead's state, lateral entry, and consent to be contacted.

Revision ID: 0007
Revises: 0006
Create Date: 2026-11-15
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0007"
down_revision: Union[str, None] = "0006"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("leads", sa.Column("state", sa.String(100), nullable=True))
    op.add_column("leads", sa.Column("lateral_entry", sa.Boolean(), nullable=False, server_default=sa.false()))
    op.add_column("leads", sa.Column("contact_consent", sa.Boolean(), nullable=False, server_default=sa.false()))
    op.add_column("leads", sa.Column("consent_at", sa.DateTime(timezone=True), nullable=True))


def downgrade() -> None:
    op.drop_column("leads", "consent_at")
    op.drop_column("leads", "contact_consent")
    op.drop_column("leads", "lateral_entry")
    op.drop_column("leads", "state")
