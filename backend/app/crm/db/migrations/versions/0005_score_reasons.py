"""crm: store the reasons behind a lead's score, so tier explanations survive.

Revision ID: 0005
Revises: 0004
Create Date: 2026-11-04
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0005"
down_revision: Union[str, None] = "0004"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("leads", sa.Column("score_reasons", postgresql.JSONB(), nullable=True))


def downgrade() -> None:
    op.drop_column("leads", "score_reasons")
