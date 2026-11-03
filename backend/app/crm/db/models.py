"""SQLAlchemy ORM models for the CRM module.

Tables (in FK dependency order):
    users -> leads -> interactions -> approvals -> audit_log

RULES (from RULES.md):
- Every write must call log_event.
- Anything that changes state goes through the approval gate.
- audit_log is append-only: no update or delete helpers.
"""
from datetime import datetime
from typing import Optional

from sqlalchemy import (
    BigInteger,
    Boolean,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    String,
    Text,
    func,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.crm.db.base import Base


# ---------------------------------------------------------------------------
# users
# ---------------------------------------------------------------------------
class User(Base):
    """CRM staff and student accounts.

    role must be one of: "admin", "counsellor", "student".
    """

    __tablename__ = "users"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    email: Mapped[str] = mapped_column(String(255), unique=True, nullable=False)
    full_name: Mapped[str] = mapped_column(String(255), nullable=False)
    role: Mapped[str] = mapped_column(String(50), nullable=False)          # admin | counsellor | student
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default="true")
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now()
    )

    # relationships
    leads: Mapped[list["Lead"]] = relationship(
        "Lead", back_populates="assigned_user", foreign_keys="Lead.assigned_to"
    )
    approvals_requested: Mapped[list["Approval"]] = relationship(
        "Approval", back_populates="requested_by_user", foreign_keys="Approval.requested_by"
    )
    approvals_resolved: Mapped[list["Approval"]] = relationship(
        "Approval", back_populates="resolved_by_user", foreign_keys="Approval.resolved_by"
    )


# ---------------------------------------------------------------------------
# leads  — columns mirror LeadProfile in contracts/models.py exactly
# ---------------------------------------------------------------------------
class Lead(Base):
    """One prospective student.

    The LeadProfile block (name … channel) must stay in sync with
    contracts/models.py:LeadProfile. Do NOT add or remove those fields
    without a contracts PR approved by all four owners.
    """

    __tablename__ = "leads"
    __table_args__ = (Index("ix_leads_score_tier", "score_tier"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)

    # --- LeadProfile fields (contracts/models.py) -----------------------
    name: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    phone: Mapped[Optional[str]] = mapped_column(String(20), nullable=True)
    email: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    city: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    program_interest: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    twelfth_percent: Mapped[Optional[float]] = mapped_column(Numeric(5, 2), nullable=True)
    entrance_exam: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    budget_lakh: Mapped[Optional[float]] = mapped_column(Numeric(6, 2), nullable=True)
    asked_scholarship: Mapped[bool] = mapped_column(
        Boolean, nullable=False, server_default="false"
    )
    channel: Mapped[str] = mapped_column(
        String(20), nullable=False, server_default="web"
    )

    # --- CRM metadata ---------------------------------------------------
    status: Mapped[str] = mapped_column(
        String(50), nullable=False, server_default="new"
    )
    score: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    score_tier: Mapped[Optional[str]] = mapped_column(String(10), nullable=True)   # hot | warm | cold
    opted_out: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default="false")
    assigned_to: Mapped[Optional[int]] = mapped_column(
        Integer, ForeignKey("users.id"), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now()
    )

    # relationships
    assigned_user: Mapped[Optional["User"]] = relationship(
        "User", back_populates="leads", foreign_keys=[assigned_to]
    )
    interactions: Mapped[list["Interaction"]] = relationship(
        "Interaction", back_populates="lead"
    )
    approvals: Mapped[list["Approval"]] = relationship(
        "Approval", back_populates="lead"
    )


# ---------------------------------------------------------------------------
# interactions
# ---------------------------------------------------------------------------
class Interaction(Base):
    """Every agent <-> lead touchpoint (inbound or outbound)."""

    __tablename__ = "interactions"
    __table_args__ = (Index("ix_interactions_lead_id", "lead_id"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    lead_id: Mapped[int] = mapped_column(Integer, ForeignKey("leads.id"), nullable=False)
    actor: Mapped[str] = mapped_column(String(50), nullable=False)     # agent | counsellor | system
    channel: Mapped[str] = mapped_column(String(20), nullable=False)   # web | whatsapp | email
    direction: Mapped[str] = mapped_column(String(10), nullable=False) # inbound | outbound
    message: Mapped[str] = mapped_column(Text, nullable=False)
    meta: Mapped[Optional[dict]] = mapped_column(JSONB, nullable=True) # slot_id, template_id, …
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )

    # relationships
    lead: Mapped["Lead"] = relationship("Lead", back_populates="interactions")


# ---------------------------------------------------------------------------
# approvals  — human-in-the-loop gate; maps to contracts/models.py:ApprovalRequest
# ---------------------------------------------------------------------------
class Approval(Base):
    """State-changing actions that require human sign-off.

    RULES: never skip the status == "approved" check before executing the action.
    """

    __tablename__ = "approvals"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    lead_id: Mapped[Optional[int]] = mapped_column(
        Integer, ForeignKey("leads.id"), nullable=True
    )
    action: Mapped[str] = mapped_column(String(255), nullable=False)   # e.g. "book_slot"
    payload: Mapped[dict] = mapped_column(JSONB, nullable=False)
    status: Mapped[str] = mapped_column(
        String(20), nullable=False, server_default="pending"
    )                                                                   # pending | approved | rejected
    reason: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    requested_by_actor: Mapped[str] = mapped_column(
        String(50), nullable=False
    )                                                                   # "agent" or user email
    requested_by: Mapped[Optional[int]] = mapped_column(
        Integer, ForeignKey("users.id"), nullable=True
    )
    resolved_by: Mapped[Optional[int]] = mapped_column(
        Integer, ForeignKey("users.id"), nullable=True
    )
    resolved_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )

    # relationships
    lead: Mapped[Optional["Lead"]] = relationship("Lead", back_populates="approvals")
    requested_by_user: Mapped[Optional["User"]] = relationship(
        "User", back_populates="approvals_requested", foreign_keys=[requested_by]
    )
    resolved_by_user: Mapped[Optional["User"]] = relationship(
        "User", back_populates="approvals_resolved", foreign_keys=[resolved_by]
    )
    audit_entries: Mapped[list["AuditLog"]] = relationship(
        "AuditLog", back_populates="approval"
    )


# ---------------------------------------------------------------------------
# audit_log  — append-only event log
# ---------------------------------------------------------------------------
class AuditLog(Base):
    """Immutable event log.  RULES: no update or delete helpers anywhere in the codebase.

    event_type values: "tool_call", "reasoning_step", "approval_decision",
                       "login", "access_denied".
    """

    __tablename__ = "audit_log"
    __table_args__ = (
        Index("ix_audit_log_created_at", "created_at"),
        Index("ix_audit_log_request_id", "request_id"),
        Index("ix_audit_log_lead_id", "lead_id"),
        Index("ix_audit_log_session_id", "session_id"),
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    actor: Mapped[str] = mapped_column(String(255), nullable=False)    # "agent" | "system" | user email
    event_type: Mapped[str] = mapped_column(String(50), nullable=False)
    tool_name: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    input: Mapped[Optional[dict]] = mapped_column(JSONB, nullable=True)
    output: Mapped[Optional[dict]] = mapped_column(JSONB, nullable=True)
    reasoning_step: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    approval_id: Mapped[Optional[int]] = mapped_column(
        Integer, ForeignKey("approvals.id"), nullable=True             # INTEGER matches approvals.id
    )
    request_id: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    lead_id: Mapped[Optional[int]] = mapped_column(
        Integer, ForeignKey("leads.id"), nullable=True                 # migration 0002
    )
    session_id: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)

    # relationships
    approval: Mapped[Optional["Approval"]] = relationship(
        "Approval", back_populates="audit_entries"
    )
