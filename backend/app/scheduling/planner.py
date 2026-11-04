"""Adaptive follow-up policy (SPEC 2.5). The policy is code; only the wording may come from the LLM.

Runs after each chat turn: the lead's pending planned follow-up is replaced, so
the wait restarts from their latest message. dispatch_due skips it if they reply first.
"""
from __future__ import annotations

from datetime import timedelta
from typing import Optional

from sqlalchemy import select

from app.crm.db.base import SessionLocal
from app.crm.db.models import Lead as LeadRow
from app.crm.service import log_event
from app.scheduling import clock
from app.scheduling.models import FollowupRow

TIER_POLICY = {"hot": ("hot_reminder", 24), "warm": ("warm_nudge", 48), "cold": ("cold_nurture", 168)}
OBJECTIONS = {"fees", "distance"}


def decide(lead: LeadRow, objection: Optional[str]) -> Optional[tuple[str, int]]:
    """(template, hours to wait) for this lead, or None. An objection outranks scholarships, which outrank tier."""
    if objection in OBJECTIONS:
        return "objection", 24
    if lead.asked_scholarship:
        return "scholarship", 24
    return TIER_POLICY.get(lead.score_tier or "")


def plan_followup(lead_id: int, objection: Optional[str] = None) -> dict:
    """Replace this lead's pending planned follow-up according to the policy. No-op for opted-out leads."""
    now = clock.now()
    with SessionLocal() as db:
        lead = db.get(LeadRow, lead_id)
        if lead is None:
            return {"ok": False, "planned": None, "reason": "lead_not_found"}
        if lead.opted_out:
            return {"ok": True, "planned": None, "reason": "opted_out"}

        pending = [f for f in db.scalars(select(FollowupRow).where(
            FollowupRow.lead_id == lead_id, FollowupRow.status == "pending").with_for_update()).all()
            if (f.payload or {}).get("planned")]
        for old in pending:                      # an objection stays relevant until it has been addressed
            objection = objection or old.payload.get("objection")

        decision = decide(lead, objection)
        if decision is None:
            return {"ok": True, "planned": None, "reason": "no_policy_applies"}

        for old in pending:
            old.status, old.processed_at = "skipped", now
            old.payload = {**old.payload, "outcome": "superseded"}
        template, hours = decision
        row = FollowupRow(lead_id=lead_id, due_at=now + timedelta(hours=hours), template=template, status="pending",
                          payload={"planned": True, "objection": objection if template == "objection" else None})
        db.add(row)
        db.commit()
        planned = {"followup_id": row.id, "template": template, "due_at": clock.to_ist(row.due_at), "wait_hours": hours}

    log_event(actor="agent", event_type="tool_call", tool_name="plan_followup",
              input={"lead_id": lead_id, "objection": objection}, output=planned,
              reasoning_step=f"policy: {template} after {hours}h", request_id=None, lead_id=lead_id)
    return {"ok": True, "planned": planned, "reason": template}
