"""Sends due follow-ups on the virtual clock.

Templates contain no institutional facts (fees, dates, scholarships). Anything factual
comes from a registered composer, which writes KB-cited wording and checks it; if it
declines, the template goes out. A follow-up is skipped if the lead opted out or has
replied since it was scheduled.
"""
from __future__ import annotations

import logging
import time
from datetime import timedelta
from typing import Callable, Optional

from sqlalchemy import exists, or_, select
from sqlalchemy.orm import Session

from app.crm.db.base import SessionLocal
from app.crm.db.models import Interaction
from app.crm.db.models import Lead as LeadRow
from app.crm.service import log_event
from app.scheduling import clock
from app.scheduling.models import FollowupRow, MessageRow
from app.scheduling.service import _store_message

log = logging.getLogger(__name__)
COMPOSED_TEMPLATES = {"warm_nudge", "scholarship", "objection"}
COMPOSE_BUDGET_SECONDS = 30       # per dispatch run: beyond this, templates go out rather than holding the run
MAX_COMPOSED_PER_RUN = 5
NURTURE_REPEAT_HOURS = 168
Composer = Callable[[str, Optional[str], Optional[str], Optional[dict]], Optional[dict]]
_composer: Optional[Composer] = None

TEMPLATES = {
    "hot_reminder": "Hi {name}, just checking in about {program}. Would you like to book a call with a "
                    "JKLU admissions counsellor this week?",
    "warm_nudge": "Hi {name}, do you have any questions about {program} at JKLU? I'm happy to help, "
                  "or a counsellor can call you.",
    "cold_nurture": "Hi {name}, this is JKLU admissions. Reply any time if you'd like to know more "
                    "about our programs.",
    "scholarship": "Hi {name}, you asked about scholarships for {program}. A counsellor can go through "
                   "your eligibility with you. Would you like a call?",
    "objection": "Hi {name}, we know fees and distance matter when choosing a university. A counsellor "
                 "can talk through your options. Would you like a call?",
}


def set_composer(composer: Optional[Composer]) -> None:
    """Register the function that writes grounded wording (the agent does this at startup)."""
    global _composer
    _composer = composer


def _composed(f: FollowupRow, lead: LeadRow, budget: dict) -> Optional[dict]:
    """KB-cited wording for this follow-up, if a composer is set and the run's budget allows it."""
    if (_composer is None or f.template not in COMPOSED_TEMPLATES or budget["left"] <= 0
            or time.monotonic() >= budget["deadline"]):
        return None
    budget["left"] -= 1
    try:
        return _composer(f.template, lead.name, lead.program_interest, f.payload)
    except Exception:
        log.warning("follow-up composer failed", exc_info=True)
        return None


def render(template: str, lead: LeadRow) -> str:
    """Fill a named template from the lead's profile; any other text is sent as written."""
    body = TEMPLATES.get(template, template)
    return body.format_map({"name": lead.name or "there", "program": lead.program_interest or "your program"}) \
        if template in TEMPLATES else body


def pick_channel(lead: LeadRow) -> str:
    """The lead's own channel; web leads are reached by email, then WhatsApp, else in the web inbox."""
    if lead.channel in ("whatsapp", "email"):
        return lead.channel
    return "email" if lead.email else "whatsapp" if lead.phone else "web"


def _replied_since(db: Session, lead_id: int, since) -> bool:
    chat = exists().where(Interaction.lead_id == lead_id, Interaction.direction == "inbound",
                          Interaction.created_at > since)
    channel = exists().where(MessageRow.lead_id == lead_id, MessageRow.direction == "inbound",
                             MessageRow.created_at > since)
    return bool(db.scalar(select(or_(chat, channel))))


def dispatch_due(limit: int = 100) -> dict:
    """Send or skip every pending follow-up due by the virtual now. Safe to run concurrently.

    Rows are claimed with FOR UPDATE SKIP LOCKED, so two runs never process the
    same follow-up. Returns counts and the processed ids.
    """
    now = clock.now()
    outcomes: list[dict] = []
    budget = {"left": MAX_COMPOSED_PER_RUN, "deadline": time.monotonic() + COMPOSE_BUDGET_SECONDS}
    with SessionLocal() as db:
        due = db.scalars(select(FollowupRow)
                         .where(FollowupRow.status == "pending", FollowupRow.due_at <= now)
                         .order_by(FollowupRow.due_at).limit(limit)
                         .with_for_update(skip_locked=True)).all()
        for f in due:
            lead = db.get(LeadRow, f.lead_id)
            if lead.opted_out:
                f.status, reason = "skipped", "opted_out"
            elif _replied_since(db, lead.id, f.created_at):
                f.status, reason = "skipped", "lead_replied"
            else:
                channel = pick_channel(lead)
                written = _composed(f, lead, budget)
                msg = _store_message(db, lead.id, channel, written["text"] if written else render(f.template, lead),
                                     {"followup_id": f.id, "template": f.template,
                                      "written_by": "llm" if written else "template",
                                      "citations": written["citations"] if written else []})
                f.status, reason, f.sent_message_id = "sent", channel, msg.id
                if f.template == "cold_nurture" and (f.payload or {}).get("planned"):    # weekly until they reply
                    db.add(FollowupRow(lead_id=lead.id, template=f.template, status="pending", payload={"planned": True},
                                       due_at=now + timedelta(hours=NURTURE_REPEAT_HOURS)))
            f.processed_at = now
            f.payload = {**(f.payload or {}), "outcome": reason}
            outcomes.append({"followup_id": f.id, "lead_id": f.lead_id, "status": f.status, "detail": reason,
                             "message_id": f.sent_message_id})
        db.commit()

    for o in outcomes:
        log_event(actor="system", event_type="followup", tool_name="dispatch_followup",
                  input={"followup_id": o["followup_id"]}, output=o, reasoning_step=o["detail"],
                  request_id=None, lead_id=o["lead_id"])
    counts = {s: sum(o["status"] == s for o in outcomes) for s in ("sent", "skipped")}
    return {**counts, "processed": outcomes, "virtual_now": clock.to_ist(now)}
