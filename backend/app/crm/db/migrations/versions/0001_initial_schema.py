"""crm: initial schema — users, leads, interactions, approvals, audit_log.

Revision ID: 0001
Revises:
Create Date: 2026-11-01

Tables are created in FK dependency order:
    users -> leads -> interactions -> approvals -> audit_log

downgrade() drops them in reverse order.
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0001"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # ------------------------------------------------------------------
    # users
    # ------------------------------------------------------------------
    op.create_table(
        "users",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("email", sa.String(255), nullable=False),
        sa.Column("full_name", sa.String(255), nullable=False),
        # role: "admin" | "counsellor" | "student"
        sa.Column("role", sa.String(50), nullable=False),
        sa.Column("password_hash", sa.String(255), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.UniqueConstraint("email", name="uq_users_email"),
    )

    # ------------------------------------------------------------------
    # leads  (LeadProfile columns + CRM metadata)
    # ------------------------------------------------------------------
    op.create_table(
        "leads",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        # --- LeadProfile (contracts/models.py) -------------------------
        sa.Column("name", sa.String(255), nullable=True),
        sa.Column("phone", sa.String(20), nullable=True),
        sa.Column("email", sa.String(255), nullable=True),
        sa.Column("city", sa.String(100), nullable=True),
        sa.Column("program_interest", sa.String(255), nullable=True),
        sa.Column("twelfth_percent", sa.Numeric(5, 2), nullable=True),
        sa.Column("entrance_exam", sa.String(100), nullable=True),
        sa.Column("budget_lakh", sa.Numeric(6, 2), nullable=True),
        sa.Column(
            "asked_scholarship",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("false"),
        ),
        sa.Column(
            "channel",
            sa.String(20),
            nullable=False,
            server_default=sa.text("'web'"),
        ),
        # --- CRM metadata ----------------------------------------------
        sa.Column(
            "status",
            sa.String(50),
            nullable=False,
            server_default=sa.text("'new'"),
        ),
        sa.Column("score", sa.Integer(), nullable=True),
        sa.Column("score_tier", sa.String(10), nullable=True),   # hot | warm | cold
        sa.Column(
            "opted_out",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("false"),
        ),
        sa.Column(
            "assigned_to",
            sa.Integer(),
            sa.ForeignKey("users.id"),
            nullable=True,
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
    )
    op.create_index("ix_leads_score_tier", "leads", ["score_tier"])

    # ------------------------------------------------------------------
    # interactions
    # ------------------------------------------------------------------
    op.create_table(
        "interactions",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column(
            "lead_id",
            sa.Integer(),
            sa.ForeignKey("leads.id"),
            nullable=False,
        ),
        sa.Column("actor", sa.String(50), nullable=False),     # agent | counsellor | system
        sa.Column("channel", sa.String(20), nullable=False),   # web | whatsapp | email
        sa.Column("direction", sa.String(10), nullable=False), # inbound | outbound
        sa.Column("message", sa.Text(), nullable=False),
        sa.Column("meta", postgresql.JSONB(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
    )
    op.create_index("ix_interactions_lead_id", "interactions", ["lead_id"])

    # ------------------------------------------------------------------
    # approvals
    # ------------------------------------------------------------------
    op.create_table(
        "approvals",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column(
            "lead_id",
            sa.Integer(),
            sa.ForeignKey("leads.id"),
            nullable=True,
        ),
        sa.Column("action", sa.String(255), nullable=False),
        sa.Column("payload", postgresql.JSONB(), nullable=False),
        sa.Column(
            "status",
            sa.String(20),
            nullable=False,
            server_default=sa.text("'pending'"),
        ),                                                      # pending | approved | rejected
        sa.Column("reason", sa.Text(), nullable=True),
        # requested_by_actor: "agent" or a user email
        sa.Column("requested_by_actor", sa.String(50), nullable=False),
        sa.Column(
            "requested_by",
            sa.Integer(),
            sa.ForeignKey("users.id"),
            nullable=True,
        ),
        sa.Column(
            "resolved_by",
            sa.Integer(),
            sa.ForeignKey("users.id"),
            nullable=True,
        ),
        sa.Column("resolved_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
    )

    # ------------------------------------------------------------------
    # audit_log  — append-only; application code must never UPDATE or DELETE
    # ------------------------------------------------------------------
    op.create_table(
        "audit_log",
        sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        # actor: "agent" | "system" | user email
        sa.Column("actor", sa.String(255), nullable=False),
        # event_type: tool_call | reasoning_step | approval_decision | login | access_denied
        sa.Column("event_type", sa.String(50), nullable=False),
        sa.Column("tool_name", sa.String(100), nullable=True),
        sa.Column("input", postgresql.JSONB(), nullable=True),
        sa.Column("output", postgresql.JSONB(), nullable=True),
        sa.Column("reasoning_step", sa.Text(), nullable=True),
        # approval_id: INTEGER to match approvals.id
        sa.Column(
            "approval_id",
            sa.Integer(),
            sa.ForeignKey("approvals.id"),
            nullable=True,
        ),
        sa.Column("request_id", sa.String(100), nullable=True),
    )
    op.create_index("ix_audit_log_created_at", "audit_log", ["created_at"])
    op.create_index("ix_audit_log_request_id", "audit_log", ["request_id"])


def downgrade() -> None:
    # Drop in reverse FK dependency order
    op.drop_index("ix_audit_log_request_id", table_name="audit_log")
    op.drop_index("ix_audit_log_created_at", table_name="audit_log")
    op.drop_table("audit_log")

    op.drop_table("approvals")

    op.drop_index("ix_interactions_lead_id", table_name="interactions")
    op.drop_table("interactions")

    op.drop_index("ix_leads_score_tier", table_name="leads")
    op.drop_table("leads")

    op.drop_table("users")
