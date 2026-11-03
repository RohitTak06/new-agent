"""sched: counsellors, slots, messages, followups, sessions, virtual_clock.

Revision ID: 0003
Revises: 0002
Create Date: 2026-11-03

Booking safety in the schema: one slot per (counsellor, start) and a booked slot
must name its lead. "One upcoming booking per lead" depends on the virtual clock,
so it is enforced in scheduling.service.book_slot under a lead row lock.
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0003"
down_revision: Union[str, None] = "0002"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _created_at() -> sa.Column:
    return sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now())


def upgrade() -> None:
    op.create_table(
        "counsellors",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=True, unique=True),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("active", sa.Boolean(), nullable=False, server_default=sa.text("true")),
    )

    op.create_table(
        "slots",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("counsellor_id", sa.Integer(), sa.ForeignKey("counsellors.id"), nullable=False),
        sa.Column("start_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("end_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("status", sa.String(10), nullable=False, server_default=sa.text("'free'")),
        sa.Column("lead_id", sa.Integer(), sa.ForeignKey("leads.id"), nullable=True),
        sa.Column("booked_at", sa.DateTime(timezone=True), nullable=True),
        sa.UniqueConstraint("counsellor_id", "start_at", name="uq_slots_counsellor_start"),
        sa.CheckConstraint("status IN ('free', 'booked')", name="ck_slots_status"),
        sa.CheckConstraint("(status = 'booked') = (lead_id IS NOT NULL)", name="ck_slots_booked_has_lead"),
    )
    op.create_index("ix_slots_status_start", "slots", ["status", "start_at"])
    op.create_index("ix_slots_lead_id", "slots", ["lead_id"])

    op.create_table(
        "messages",
        sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column("lead_id", sa.Integer(), sa.ForeignKey("leads.id"), nullable=False),
        sa.Column("channel", sa.String(20), nullable=False),
        sa.Column("direction", sa.String(10), nullable=False),
        sa.Column("text", sa.Text(), nullable=False),
        sa.Column("sent_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("meta", postgresql.JSONB(), nullable=True),
        _created_at(),
    )
    op.create_index("ix_messages_lead_id", "messages", ["lead_id"])

    op.create_table(
        "followups",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("lead_id", sa.Integer(), sa.ForeignKey("leads.id"), nullable=False),
        sa.Column("due_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("template", sa.Text(), nullable=False),
        sa.Column("status", sa.String(10), nullable=False, server_default=sa.text("'pending'")),
        sa.Column("payload", postgresql.JSONB(), nullable=True),
        sa.Column("sent_message_id", sa.BigInteger(), sa.ForeignKey("messages.id"), nullable=True),
        _created_at(),
        sa.Column("processed_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index("ix_followups_status_due", "followups", ["status", "due_at"])
    op.create_index("ix_followups_lead_id", "followups", ["lead_id"])

    op.create_table(
        "sessions",
        sa.Column("session_id", sa.String(64), primary_key=True),
        sa.Column("lead_id", sa.Integer(), sa.ForeignKey("leads.id"), nullable=False),
        sa.Column("channel", sa.String(20), nullable=False),
        _created_at(),
        sa.Column("last_seen_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )
    op.create_index("ix_sessions_lead_id", "sessions", ["lead_id"])

    op.create_table(
        "virtual_clock",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("offset_seconds", sa.BigInteger(), nullable=False, server_default=sa.text("0")),
    )
    op.execute("INSERT INTO virtual_clock (id, offset_seconds) VALUES (1, 0)")


def downgrade() -> None:
    op.drop_table("virtual_clock")
    op.drop_index("ix_sessions_lead_id", table_name="sessions")
    op.drop_table("sessions")
    op.drop_index("ix_followups_lead_id", table_name="followups")
    op.drop_index("ix_followups_status_due", table_name="followups")
    op.drop_table("followups")
    op.drop_index("ix_messages_lead_id", table_name="messages")
    op.drop_table("messages")
    op.drop_index("ix_slots_lead_id", table_name="slots")
    op.drop_index("ix_slots_status_start", table_name="slots")
    op.drop_table("slots")
    op.drop_table("counsellors")
