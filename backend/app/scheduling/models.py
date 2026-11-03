"""SQLAlchemy models for scheduling and channels (migration 0003).

All timestamps are UTC. `*_at` business times (slot start, follow-up due,
message sent) are on the virtual clock; `created_at` columns are real time.
"""
from datetime import datetime
from typing import Optional

from sqlalchemy import (
    BigInteger, Boolean, DateTime, ForeignKey, Index, Integer, String, Text, UniqueConstraint, func, text,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.crm.db.base import Base


class Counsellor(Base):
    __tablename__ = "counsellors"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[Optional[int]] = mapped_column(Integer, ForeignKey("users.id"), nullable=True, unique=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    active: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default=text("true"))


class SlotRow(Base):
    """A bookable counsellor session. status: free | booked."""

    __tablename__ = "slots"
    __table_args__ = (
        UniqueConstraint("counsellor_id", "start_at", name="uq_slots_counsellor_start"),
        Index("ix_slots_status_start", "status", "start_at"),
        Index("ix_slots_lead_id", "lead_id"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    counsellor_id: Mapped[int] = mapped_column(Integer, ForeignKey("counsellors.id"), nullable=False)
    start_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    end_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    status: Mapped[str] = mapped_column(String(10), nullable=False, server_default=text("'free'"))
    lead_id: Mapped[Optional[int]] = mapped_column(Integer, ForeignKey("leads.id"), nullable=True)
    booked_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)


class MessageRow(Base):
    """Mock WhatsApp / email / web message. Nothing is really sent."""

    __tablename__ = "messages"
    __table_args__ = (Index("ix_messages_lead_id", "lead_id"),)

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    lead_id: Mapped[int] = mapped_column(Integer, ForeignKey("leads.id"), nullable=False)
    channel: Mapped[str] = mapped_column(String(20), nullable=False)      # web | whatsapp | email
    direction: Mapped[str] = mapped_column(String(10), nullable=False)    # inbound | outbound
    text: Mapped[str] = mapped_column(Text, nullable=False)
    sent_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)   # virtual
    meta: Mapped[Optional[dict]] = mapped_column(JSONB, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())


class FollowupRow(Base):
    """A scheduled outbound touch. status: pending | sent | skipped | failed."""

    __tablename__ = "followups"
    __table_args__ = (Index("ix_followups_status_due", "status", "due_at"),
                      Index("ix_followups_lead_id", "lead_id"))

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    lead_id: Mapped[int] = mapped_column(Integer, ForeignKey("leads.id"), nullable=False)
    due_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)     # virtual
    template: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[str] = mapped_column(String(10), nullable=False, server_default=text("'pending'"))
    payload: Mapped[Optional[dict]] = mapped_column(JSONB, nullable=True)
    sent_message_id: Mapped[Optional[int]] = mapped_column(BigInteger, ForeignKey("messages.id"), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())
    processed_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)  # virtual


class SessionRow(Base):
    """A chat session, bound to one lead."""

    __tablename__ = "sessions"

    session_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    lead_id: Mapped[int] = mapped_column(Integer, ForeignKey("leads.id"), nullable=False, index=True)
    channel: Mapped[str] = mapped_column(String(20), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())
    last_seen_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())


class VirtualClock(Base):
    """Single row (id=1): offset added to real time. Stored so reloads keep the demo's time."""

    __tablename__ = "virtual_clock"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    offset_seconds: Mapped[int] = mapped_column(BigInteger, nullable=False, server_default=text("0"))
