"""Sets the stage for the 5-minute demo on top of the normal seed. Synthetic data only.

    python scripts/demo.py --reset     # the usual way in: rebuilds the database, then calls this

Leaves: every seed lead scored for real, with reasons; a slot already held so the booking
clash is guaranteed; follow-ups due within 24 hours, so fast-forward always has something
to send and one thing to refuse; and one bulk message waiting for approval.
"""
from __future__ import annotations

from datetime import timedelta
from typing import Optional
from urllib.parse import urlsplit

from sqlalchemy import select

from app.contracts import tools
from app.contracts.models import Slot
from app.crm import service as crm
from app.crm.db.base import SessionLocal
from app.crm.db.models import Lead as LeadRow
from app.crm.seed import _STUDENTS
from app.scheduling import clock
from app.scheduling import service as scheduling
from app.scheduling.seed import seed_slots

DEMO_SLOT_DAYS = 14                     # room for repeated fast-forwards in a rehearsal
FOLLOWUP_DUE_HOURS = 23                 # inside the demo's 24-hour fast-forward
CLASH_COUNSELLOR = "Ms. Rekha Verma"
CLASH_HOUR = 11

CLASH_HOLDER = "Second Student"
HOT_SILENT_LEAD = "Diya Mehta"          # WhatsApp: gets a fixed-template reminder
SCHOLARSHIP_LEAD = "Aarav Sharma"       # gets wording the agent writes from the knowledge base
OPTED_OUT_LEAD = "Nikhil Bansal"        # fast-forward shows this one being refused
BULK_LEADS = ["Kavya Reddy", "Rahul Dubey", "Amit Kapoor"]
BULK_TEXT = ("Hi, a JKLU admissions counsellor is available this week if you have any questions. "
             "Reply to this message and we'll set up a call.")


def assert_safe_to_reset(database_url: str) -> None:
    """The reset drops a database. Refuse anything but the local demo one."""
    url = urlsplit(database_url)
    if url.hostname not in ("localhost", "127.0.0.1") or url.path.lstrip("/") != "admissions":
        raise SystemExit(f"Refusing to reset {url.hostname}{url.path}: only the local 'admissions' database may be reset.")


def _lead_id(db, name: str) -> int:
    lead_id = db.scalars(select(LeadRow.id).where(LeadRow.name == name).order_by(LeadRow.id)).first()
    if lead_id is None:
        raise ValueError(f"Seed lead {name!r} not found")
    return lead_id


def score_seed_leads() -> int:
    """Score seed leads with the real engine, so every card shows real reasons. Students stay unscored for the demo."""
    students = {email for email, *_ in _STUDENTS}
    scored = 0
    for lead in crm.list_leads():
        if lead.profile.email not in students:
            result = tools.score_lead(lead.profile)
            tools.update_lead_score(lead.id, result.score, result.tier, result.reasons)
            scored += 1
    return scored


def _clash_slot() -> Optional[Slot]:
    """The demo's held slot: the next working day's late-morning session with one counsellor."""
    today = clock.now().astimezone(clock.IST).date()
    until = today + timedelta(days=DEMO_SLOT_DAYS)
    starts_at = f"T{CLASH_HOUR}:00:00"
    for offset in range(1, DEMO_SLOT_DAYS):
        day = (today + timedelta(days=offset)).isoformat()
        for slot in scheduling.get_slots(day, until.isoformat()):
            if slot.counsellor == CLASH_COUNSELLOR and slot.start.startswith(day + starts_at):
                return slot
    return None


def stage_demo() -> dict:
    """Create the demo's starting conditions. Returns what the presenter needs to know."""
    seed_slots(DEMO_SLOT_DAYS)
    due = (clock.now() + timedelta(hours=FOLLOWUP_DUE_HOURS)).isoformat()
    with SessionLocal() as db:
        holder = _lead_id(db, CLASH_HOLDER)
        hot = _lead_id(db, HOT_SILENT_LEAD)
        scholarship = _lead_id(db, SCHOLARSHIP_LEAD)
        opted_out = _lead_id(db, OPTED_OUT_LEAD)
        bulk = [_lead_id(db, name) for name in BULK_LEADS]

    slot = _clash_slot()
    if slot is None or not scheduling.book_slot(holder, slot.slot_id).ok:
        raise RuntimeError("Could not set up the booking clash")

    for lead_id, template in ((hot, "hot_reminder"), (scholarship, "scholarship"), (opted_out, "warm_nudge")):
        if not scheduling.schedule_followup(lead_id, due, template)["ok"]:
            raise RuntimeError(f"Could not schedule {template} for lead {lead_id}")
    crm.opt_out_lead(opted_out)

    approval = tools.request_bulk_message(bulk, "email", BULK_TEXT)
    return {"clash_slot": slot, "bulk_approval_id": approval.approval_id}
