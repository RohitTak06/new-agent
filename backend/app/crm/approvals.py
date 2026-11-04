"""Approval gate (SPEC 5): list, approve and reject, with a registered executor per action.

A sensitive action runs only here, after a counsellor approves it, while the
approval row is locked and still `pending`, so it can never run twice. If it
fails, the approval stays pending and the failure is audited. Executors never
state institutional facts of their own: replies are written by the counsellor.
"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Callable, Optional

from sqlalchemy import select

from app.contracts import tools
from app.crm import service as crm
from app.crm.auth import CurrentUser
from app.crm.db.base import SessionLocal
from app.crm.db.models import Approval
from app.crm.db.models import Lead as LeadRow
from app.scheduling import clock
from app.scheduling import service as scheduling
from app.scheduling.followups import pick_channel


class ApprovalError(Exception):
    """Refused or failed decision. `status_code` is what the API should return."""

    def __init__(self, status_code: int, detail: str):
        super().__init__(detail)
        self.status_code = status_code
        self.detail = detail


def _as_dict(row: Approval) -> dict:
    return {"id": row.id, "action": row.action, "payload": row.payload, "status": row.status,
            "lead_id": row.lead_id, "reason": row.reason, "requested_by_actor": row.requested_by_actor,
            "resolved_by": row.resolved_by,
            "resolved_at": row.resolved_at.isoformat() if row.resolved_at else None,
            "created_at": row.created_at.isoformat()}


def list_approvals(status: Optional[str] = None, limit: int = 200) -> list[dict]:
    """Approvals, newest first, optionally filtered by status."""
    stmt = select(Approval).order_by(Approval.id.desc()).limit(limit)
    if status:
        stmt = stmt.where(Approval.status == status)
    with SessionLocal() as db:
        return [_as_dict(r) for r in db.scalars(stmt).all()]


# ---------------------------------------------------------------- notifications
def _notify(lead_id: Optional[int], text: str, approval_id: int) -> bool:
    """Message the lead on their channel and log it. False if opted out or unreachable (S9 is a hard stop)."""
    if lead_id is None:
        return False
    with SessionLocal() as db:
        lead = db.get(LeadRow, lead_id)
        if lead is None:
            return False
        channel = pick_channel(lead)
    if not tools.send_message(channel, lead_id, text).ok:
        return False
    crm.add_interaction(lead_id, actor="counsellor", channel=channel, direction="outbound", message=text,
                        meta={"approval_id": approval_id})
    return True


def _when(iso: str) -> str:
    return clock.parse(iso).astimezone(clock.IST).strftime("%a %d %b, %I:%M %p IST")


def _lead_id(payload: dict) -> int:
    lead_id = payload.get("lead_id")
    if not isinstance(lead_id, int):
        raise ValueError("payload needs lead_id")
    return lead_id


# ---------------------------------------------------------------- executors
def _fee_waiver(payload: dict, approval_id: int, note: Optional[str], reply: Optional[str]) -> dict:
    """Annotate the lead and tell the student. Terms come from the counsellor, never from the agent."""
    lead_id = _lead_id(payload)
    with SessionLocal() as db:
        lead = db.get(LeadRow, lead_id)
        if lead is None:
            raise ValueError(f"Lead {lead_id} not found")
        channel = pick_channel(lead)
    crm.add_interaction(lead_id, actor="counsellor", channel=channel, direction="outbound",
                        message=f"Fee waiver approved by a counsellor.{' Note: ' + note if note else ''}",
                        meta={"approval_id": approval_id, "fee_waiver": "approved"})
    text = reply or "A counsellor has approved your fee waiver request and will contact you with the details."
    return {"lead_id": lead_id, "notified": tools.send_message(channel, lead_id, text).ok}


def _booking_override(payload: dict, approval_id: int, note: Optional[str], reply: Optional[str]) -> dict:
    """Force-book the slot, then tell the new holder and anyone who lost it."""
    lead_id = _lead_id(payload)
    moved = scheduling.override_booking(lead_id, str(payload.get("slot_id")))
    slot = moved["slot"]
    notified = _notify(lead_id, f"Your session with {slot['counsellor']} is confirmed for {_when(slot['start'])}.",
                       approval_id)
    displaced = moved["displaced_lead_id"]
    displaced_notified = None
    if displaced is not None:
        options = ", ".join(f"{_when(a['start'])} with {a['counsellor']}" for a in moved["alternatives"])
        displaced_notified = _notify(displaced, f"Your session on {_when(slot['start'])} had to be changed by a "
                                     f"counsellor. Free slots nearby: {options}.", approval_id)
    return {**moved, "notified": notified, "displaced_notified": displaced_notified}


def _bulk_message(payload: dict, approval_id: int, note: Optional[str], reply: Optional[str]) -> dict:
    """Send the approved text to the listed leads. Opted-out leads are refused and reported."""
    lead_ids, channel, text = payload.get("lead_ids"), payload.get("channel"), payload.get("text")
    if not lead_ids or not isinstance(lead_ids, list) or not channel or not text:
        raise ValueError("payload needs lead_ids, channel and text")
    sent, refused = [], []
    for lead_id in lead_ids:
        res = tools.send_message(channel, lead_id, text)
        if res.ok:
            sent.append(lead_id)
        else:
            refused.append({"lead_id": lead_id, "error": res.error})
    return {"sent": sent, "refused": refused}


def _escalate_question(payload: dict, approval_id: int, note: Optional[str], reply: Optional[str]) -> dict:
    """Send the counsellor's own answer to the student. Answers outside the KB always come from a person."""
    if not reply or not reply.strip():
        raise ApprovalError(422, "escalate_question needs a reply written by the counsellor")
    lead_id = _lead_id(payload)
    return {"lead_id": lead_id, "notified": _notify(lead_id, reply.strip(), approval_id)}


Executor = Callable[[dict, int, Optional[str], Optional[str]], dict]
EXECUTORS: dict[str, Executor] = {
    "fee_waiver": _fee_waiver,
    "booking_override": _booking_override,
    "bulk_message": _bulk_message,
    "escalate_question": _escalate_question,
}


# ---------------------------------------------------------------- decisions
def _resolve(approval_id: int, user: CurrentUser, status: str, reason: Optional[str],
             work: Callable[[Approval], dict]) -> dict:
    """Lock the pending row, run `work`, then record the decision in one transaction."""
    with SessionLocal() as db:
        # FOR NO KEY UPDATE: audit rows referencing this approval (FK checks) must not block on it.
        row = db.scalars(select(Approval).where(Approval.id == approval_id).with_for_update(key_share=True)).first()
        if row is None:
            raise ApprovalError(404, f"Approval {approval_id} not found")
        if row.status != "pending":
            raise ApprovalError(409, f"Approval {approval_id} is already {row.status}")
        action, lead_id, payload = row.action, row.lead_id, row.payload
        try:
            outcome = work(row)
        except ApprovalError:
            raise
        except Exception as exc:
            db.rollback()
            crm.log_event(actor=user.email, event_type="approval_execution_failed", tool_name=action,
                          input={"approval_id": approval_id}, output={"error": f"{type(exc).__name__}: {exc}"[:300]},
                          reasoning_step=None, request_id=None, approval_id=approval_id, lead_id=lead_id)
            raise ApprovalError(422, f"Could not run {action}: {exc}")
        row.status = status
        row.reason = reason
        row.resolved_by = user.id
        row.resolved_at = datetime.now(timezone.utc)
        db.commit()
        result = {**_as_dict(row), "outcome": outcome}

    crm.log_event(actor=user.email, event_type="approval_decision", tool_name=action,
                  input={"approval_id": approval_id, "decision": status, "reason": reason, "payload": payload},
                  output=outcome, reasoning_step=reason, request_id=None, approval_id=approval_id, lead_id=lead_id)
    return result


def approve(approval_id: int, user: CurrentUser, note: Optional[str] = None, reply: Optional[str] = None) -> dict:
    """Approve and execute. Raises ApprovalError on a resolved, unknown or failing action."""
    def work(row: Approval) -> dict:
        executor = EXECUTORS.get(row.action)
        if executor is None:
            raise ApprovalError(422, f"No executor registered for action '{row.action}'")
        return executor(row.payload, row.id, note, reply)
    return _resolve(approval_id, user, "approved", note, work)


def reject(approval_id: int, user: CurrentUser, reason: str) -> dict:
    """Reject without executing anything, tell the student why and offer a call."""
    def work(row: Approval) -> dict:
        text = (f"A counsellor reviewed your request and could not approve it: {reason} "
                "Would you like a call to talk through other options?")
        return {"notified": _notify(row.lead_id, text, row.id)}
    return _resolve(approval_id, user, "rejected", reason, work)
