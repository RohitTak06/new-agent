"""Read-only views for staff: audit trail and funnel analytics."""
from __future__ import annotations

from datetime import datetime
from typing import Optional

from sqlalchemy import func, select

from app.crm.db.base import SessionLocal
from app.crm.db.models import Approval, AuditLog
from app.crm.db.models import Lead as LeadRow
from app.scheduling.models import SlotRow

MAX_AUDIT_ROWS = 500


def list_audit(lead_id: Optional[int] = None, session_id: Optional[str] = None, event_type: Optional[str] = None,
               date_from: Optional[datetime] = None, date_to: Optional[datetime] = None,
               limit: int = 100, offset: int = 0) -> list[dict]:
    """Audit rows, newest first, filtered by lead, session, type and real-time range."""
    stmt = select(AuditLog).order_by(AuditLog.id.desc())
    if lead_id is not None:
        stmt = stmt.where(AuditLog.lead_id == lead_id)
    if session_id is not None:
        stmt = stmt.where(AuditLog.session_id == session_id)
    if event_type is not None:
        stmt = stmt.where(AuditLog.event_type == event_type)
    if date_from is not None:
        stmt = stmt.where(AuditLog.created_at >= date_from)
    if date_to is not None:
        stmt = stmt.where(AuditLog.created_at <= date_to)
    with SessionLocal() as db:
        rows = db.scalars(stmt.limit(min(limit, MAX_AUDIT_ROWS)).offset(offset)).all()
        return [{"id": r.id, "created_at": r.created_at.isoformat(), "actor": r.actor, "event_type": r.event_type,
                 "tool_name": r.tool_name, "input": r.input, "output": r.output,
                 "reasoning_step": r.reasoning_step, "approval_id": r.approval_id, "request_id": r.request_id,
                 "lead_id": r.lead_id, "session_id": r.session_id} for r in rows]


def _counts(db, column) -> dict:
    return {str(key): n for key, n in db.execute(select(column, func.count()).group_by(column)).all()}


def funnel() -> dict:
    """Lead counts by status, tier and channel, plus opt-outs, bookings and approvals."""
    with SessionLocal() as db:
        return {
            "total_leads": db.scalar(select(func.count(LeadRow.id))),
            "by_status": _counts(db, LeadRow.status),
            "by_tier": _counts(db, LeadRow.score_tier),
            "by_channel": _counts(db, LeadRow.channel),
            "opted_out": db.scalar(select(func.count(LeadRow.id)).where(LeadRow.opted_out.is_(True))),
            "booked_sessions": db.scalar(select(func.count(SlotRow.id)).where(SlotRow.status == "booked")),
            "approvals": _counts(db, Approval.status),
        }
