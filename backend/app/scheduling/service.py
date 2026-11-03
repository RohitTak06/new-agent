"""Scheduling and channels: real implementations of the contracts/stubs.py signatures.

    get_slots(date_from, date_to) -> list[Slot]
    book_slot(lead_id, slot_id) -> BookingResult
    send_message(channel, lead_id, text) -> MessageResult
    schedule_followup(lead_id, when, template) -> dict

Every write is audit-logged. Nothing is really sent: messages are stored rows.
"""
from __future__ import annotations

from datetime import datetime
from typing import Optional

from sqlalchemy import func, select, update
from sqlalchemy.orm import Session

from app.contracts.models import BookingResult, MessageResult, Slot
from app.crm.db.base import SessionLocal
from app.crm.db.models import Lead as LeadRow
from app.crm.service import log_event
from app.scheduling import clock
from app.scheduling.models import Counsellor, FollowupRow, MessageRow, SlotRow

CHANNELS = {"web", "whatsapp", "email"}
MAX_SLOTS = 50
ALTERNATIVES = 3
MAX_TEXT = 2000


def _slot(row: SlotRow, counsellor: str) -> Slot:
    return Slot(slot_id=str(row.id), counsellor=counsellor,
                start=clock.to_ist(row.start_at), end=clock.to_ist(row.end_at))


def _free_slots_query(after: datetime):
    return (select(SlotRow, Counsellor.name)
            .join(Counsellor, Counsellor.id == SlotRow.counsellor_id)
            .where(SlotRow.status == "free", SlotRow.start_at > after, Counsellor.active.is_(True)))


def get_slots(date_from: str, date_to: str) -> list[Slot]:
    """Free, future slots starting in [date_from, date_to]. Dates are IST days (date_to inclusive)."""
    now = clock.now()
    start = max(clock.parse(date_from), now)
    end = clock.parse(date_to, end_of_day=True)
    with SessionLocal() as db:
        rows = db.execute(_free_slots_query(now)
                          .where(SlotRow.start_at >= start, SlotRow.start_at < end)
                          .order_by(SlotRow.start_at, SlotRow.counsellor_id).limit(MAX_SLOTS)).all()
    return [_slot(r, name) for r, name in rows]


def _alternatives(db: Session, target: datetime, exclude: int, now: datetime) -> list[Slot]:
    distance = func.abs(func.extract("epoch", SlotRow.start_at - target))
    rows = db.execute(_free_slots_query(now).where(SlotRow.id != exclude)
                      .order_by(distance, SlotRow.start_at).limit(ALTERNATIVES)).all()
    return [_slot(r, name) for r, name in rows]


def _counsellor_name(db: Session, row: SlotRow) -> str:
    return db.get(Counsellor, row.counsellor_id).name


def book_slot(lead_id: int, slot_id: str) -> BookingResult:
    """Book a free future slot atomically.

    The lead row is locked first, so one lead's concurrent requests run one at
    a time (one upcoming booking per lead). The slot is claimed with a single
    conditional UPDATE, so two leads can never both get it. Re-booking the
    slot this lead already holds returns ok (safe for agent retries).
    """
    result = _book(lead_id, slot_id)
    log_event(actor="system", event_type="tool_call", tool_name="book_slot",
              input={"lead_id": lead_id, "slot_id": slot_id},
              output=result.model_dump(), reasoning_step=result.reason, request_id=None, lead_id=None)
    return result


def _book(lead_id: int, slot_id: str) -> BookingResult:
    try:
        sid = int(slot_id)
    except (TypeError, ValueError):
        return BookingResult(ok=False, reason="slot_not_found")

    with SessionLocal() as db:
        lead = db.get(LeadRow, lead_id, with_for_update=True)
        if lead is None:
            return BookingResult(ok=False, reason="lead_not_found")
        now = clock.now()

        target = db.get(SlotRow, sid)
        if target is None:
            return BookingResult(ok=False, reason="slot_not_found")
        if target.status == "booked" and target.lead_id == lead_id:
            return BookingResult(ok=True, slot=_slot(target, _counsellor_name(db, target)))

        held = db.scalars(select(SlotRow).where(SlotRow.lead_id == lead_id, SlotRow.status == "booked",
                                                SlotRow.start_at > now)).first()
        if held is not None:
            return BookingResult(ok=False, reason="already_booked",
                                 slot=_slot(held, _counsellor_name(db, held)))
        if target.start_at <= now:
            return BookingResult(ok=False, reason="slot_in_past",
                                 alternatives=_alternatives(db, now, sid, now))

        claimed = db.execute(
            update(SlotRow)
            .where(SlotRow.id == sid, SlotRow.status == "free", SlotRow.start_at > now)
            .values(status="booked", lead_id=lead_id, booked_at=now)
            .returning(SlotRow.id)
        ).first()
        if claimed is None:
            db.rollback()
            return BookingResult(ok=False, reason="slot_taken",
                                 alternatives=_alternatives(db, target.start_at, sid, now))
        db.commit()
        db.refresh(target)
        return BookingResult(ok=True, slot=_slot(target, _counsellor_name(db, target)))


def _store_message(db: Session, lead_id: int, channel: str, text: str, meta: Optional[dict]) -> MessageRow:
    row = MessageRow(lead_id=lead_id, channel=channel, direction="outbound", text=text,
                     sent_at=clock.now(), meta=meta)
    db.add(row)
    db.flush()
    return row


def send_message(channel: str, lead_id: int, text: str) -> MessageResult:
    """Store an outbound mock message. Refuses opted-out leads (hard stop)."""
    error = None
    message_id = None
    if channel not in CHANNELS:
        error = "invalid_channel"
    elif not text or not text.strip() or len(text) > MAX_TEXT:
        error = "invalid_text"
    else:
        with SessionLocal() as db:
            lead = db.get(LeadRow, lead_id)
            if lead is None:
                error = "lead_not_found"
            elif lead.opted_out:
                error = "opted_out"
            else:
                message_id = str(_store_message(db, lead_id, channel, text.strip(), None).id)
                db.commit()
    result = MessageResult(ok=error is None, message_id=message_id, error=error)
    log_event(actor="system", event_type="tool_call", tool_name="send_message",
              input={"channel": channel, "lead_id": lead_id, "text": text[:MAX_TEXT]},
              output=result.model_dump(), reasoning_step=error, request_id=None, lead_id=None)
    return result


def schedule_followup(lead_id: int, when: str, template: str) -> dict:
    """Create a pending follow-up due at `when` (ISO; naive = IST) on the virtual clock."""
    result: dict
    try:
        due = clock.parse(when)
    except ValueError:
        result = {"ok": False, "error": "invalid_when", "when": when, "template": template}
    else:
        if not template or len(template) > MAX_TEXT:
            result = {"ok": False, "error": "invalid_template", "when": when, "template": template}
        else:
            with SessionLocal() as db:
                lead = db.get(LeadRow, lead_id)
                if lead is None:
                    result = {"ok": False, "error": "lead_not_found", "when": when, "template": template}
                elif lead.opted_out:
                    result = {"ok": False, "error": "opted_out", "when": when, "template": template}
                else:
                    row = FollowupRow(lead_id=lead_id, due_at=due, template=template, status="pending")
                    db.add(row)
                    db.commit()
                    result = {"ok": True, "followup_id": row.id, "when": clock.to_ist(due), "template": template}
    log_event(actor="system", event_type="tool_call", tool_name="schedule_followup",
              input={"lead_id": lead_id, "when": when, "template": template},
              output=result, reasoning_step=result.get("error"), request_id=None, lead_id=None)
    return result


def list_messages(lead_id: int) -> list[dict]:
    """All mock messages for a lead, oldest first."""
    with SessionLocal() as db:
        rows = db.scalars(select(MessageRow).where(MessageRow.lead_id == lead_id)
                          .order_by(MessageRow.sent_at, MessageRow.id)).all()
        return [{"id": r.id, "lead_id": r.lead_id, "channel": r.channel, "direction": r.direction,
                 "text": r.text, "sent_at": clock.to_ist(r.sent_at), "meta": r.meta} for r in rows]


def list_followups(lead_id: Optional[int] = None, status: Optional[str] = None) -> list[dict]:
    """Follow-ups, optionally filtered by lead and status, by due time."""
    stmt = select(FollowupRow).order_by(FollowupRow.due_at, FollowupRow.id)
    if lead_id is not None:
        stmt = stmt.where(FollowupRow.lead_id == lead_id)
    if status is not None:
        stmt = stmt.where(FollowupRow.status == status)
    with SessionLocal() as db:
        return [{"id": r.id, "lead_id": r.lead_id, "due_at": clock.to_ist(r.due_at), "template": r.template,
                 "status": r.status, "payload": r.payload, "sent_message_id": r.sent_message_id,
                 "processed_at": clock.to_ist(r.processed_at) if r.processed_at else None}
                for r in db.scalars(stmt.limit(500)).all()]
