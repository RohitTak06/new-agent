"""sched: a simulated video-meeting link on each booked session.

Revision ID: 0008
Revises: 0007
Create Date: 2026-11-15
"""
import secrets
import string
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0008"
down_revision: Union[str, None] = "0007"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _link() -> str:
    """Same shape as scheduling.service.new_meeting_url (kept here so the migration never changes with the app)."""
    part = lambda n: "".join(secrets.choice(string.ascii_lowercase) for _ in range(n))  # noqa: E731
    return f"https://meet.jklu.example/{part(3)}-{part(4)}-{part(3)}"


def upgrade() -> None:
    op.add_column("slots", sa.Column("meeting_url", sa.String(100), nullable=True))
    bind = op.get_bind()
    for (slot_id,) in bind.execute(sa.text("SELECT id FROM slots WHERE status = 'booked'")).all():
        bind.execute(sa.text("UPDATE slots SET meeting_url = :url WHERE id = :id"), {"url": _link(), "id": slot_id})


def downgrade() -> None:
    op.drop_column("slots", "meeting_url")
