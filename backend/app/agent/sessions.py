"""Chat sessions: each session_id belongs to exactly one lead."""
from __future__ import annotations

from typing import Optional

from sqlalchemy import func

from app.crm.db.base import SessionLocal
from app.scheduling.models import SessionRow


class SessionLeadMismatch(Exception):
    """The session_id is already bound to a different lead."""


def lead_for(session_id: str) -> Optional[int]:
    """Lead bound to this session, or None for a new session."""
    with SessionLocal() as db:
        row = db.get(SessionRow, session_id)
        return row.lead_id if row else None


def bind(session_id: str, lead_id: int, channel: str) -> None:
    """Create the session for this lead, or touch it. Raises SessionLeadMismatch on another lead's session."""
    with SessionLocal() as db:
        row = db.get(SessionRow, session_id, with_for_update=True)
        if row is None:
            db.add(SessionRow(session_id=session_id, lead_id=lead_id, channel=channel))
        elif row.lead_id != lead_id:
            raise SessionLeadMismatch(session_id)
        else:
            row.last_seen_at = func.now()
        db.commit()
