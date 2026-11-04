"""CRM service layer.

Public functions match the stub signatures in contracts/stubs.py exactly:
    upsert_lead(data: LeadProfile, lead_id: int | None = None) -> Lead
    get_lead(lead_id: int) -> Lead
    request_approval(action: str, payload: dict) -> ApprovalRequest

Internal helpers (not exported via tools.py):
    log_event(...)  -> None   append-only audit write
    update_lead_score(lead_id, score, tier) -> None

RULES (from RULES.md):
- Every write calls log_event.
- Anything that changes state goes through the approval gate — EXCEPT opt-out,
  which applies immediately (reversing an opt-out requires approval).
- audit_log is append-only: no update or delete anywhere.
- Do NOT import from app.intel.
"""
from __future__ import annotations

import hashlib
import hmac
import os
import secrets
from typing import Optional

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.contracts.models import ApprovalRequest, Lead, LeadProfile, LeadScore
from app.crm.db.base import SessionLocal
from app.crm.db.models import (
    Approval,
    AuditLog,
    Interaction,
    Lead as LeadRow,
)


# ---------------------------------------------------------------------------
# Internal: password utilities (used by seed; exported so seed can import them)
# ---------------------------------------------------------------------------

_PBKDF2_ITERATIONS = 260_000
_PBKDF2_HASH = "sha256"


def hash_password(plain: str) -> str:
    """Return a storable hash string: pbkdf2:sha256:<iters>$<salt_hex>$<key_hex>."""
    salt = secrets.token_hex(16)
    key = hashlib.pbkdf2_hmac(
        _PBKDF2_HASH,
        plain.encode("utf-8"),
        salt.encode("utf-8"),
        _PBKDF2_ITERATIONS,
    ).hex()
    return f"pbkdf2:{_PBKDF2_HASH}:{_PBKDF2_ITERATIONS}${salt}${key}"


def verify_password(plain: str, stored: str) -> bool:
    """Return True iff plain matches the stored hash (timing-safe)."""
    try:
        # stored format: pbkdf2:sha256:260000$salt$key
        parts = stored.split("$")
        header = parts[0]          # pbkdf2:sha256:260000
        salt = parts[1]
        expected_key = parts[2]
        iters = int(header.split(":")[-1])
        alg = header.split(":")[1]
        candidate = hashlib.pbkdf2_hmac(
            alg,
            plain.encode("utf-8"),
            salt.encode("utf-8"),
            iters,
        ).hex()
        return hmac.compare_digest(candidate, expected_key)
    except Exception:
        return False


# ---------------------------------------------------------------------------
# Internal: audit log (append-only)
# ---------------------------------------------------------------------------

def log_event(
    actor: str,
    event_type: str,
    tool_name: Optional[str],
    input: Optional[dict],
    output: Optional[dict],
    reasoning_step: Optional[str],
    request_id: Optional[str],
    approval_id: Optional[int] = None,
    lead_id: Optional[int] = None,
    session_id: Optional[str] = None,
) -> None:
    """Append one row to audit_log. Never updates or deletes."""
    db: Session = SessionLocal()
    try:
        entry = AuditLog(
            actor=actor,
            event_type=event_type,
            tool_name=tool_name,
            input=input,
            output=output,
            reasoning_step=reasoning_step,
            request_id=request_id,
            approval_id=approval_id,
            lead_id=lead_id,
            session_id=session_id,
        )
        db.add(entry)
        db.commit()
    finally:
        db.close()


# ---------------------------------------------------------------------------
# Internal: convert ORM row -> contracts Lead
# ---------------------------------------------------------------------------

def _row_to_lead(row: LeadRow) -> Lead:
    profile = LeadProfile(
        name=row.name,
        phone=row.phone,
        email=row.email,
        city=row.city,
        program_interest=row.program_interest,
        twelfth_percent=float(row.twelfth_percent) if row.twelfth_percent is not None else None,
        entrance_exam=row.entrance_exam,
        budget_lakh=float(row.budget_lakh) if row.budget_lakh is not None else None,
        asked_scholarship=row.asked_scholarship,
        channel=row.channel,
    )
    score_obj: Optional[LeadScore] = None
    if row.score is not None and row.score_tier is not None:
        score_obj = LeadScore(
            score=row.score,
            tier=row.score_tier,
            reasons=["stored score"],
        )
    return Lead(id=row.id, profile=profile, score=score_obj, status=row.status)


# ---------------------------------------------------------------------------
# Public: upsert_lead  — stub-compatible signature
# ---------------------------------------------------------------------------

def upsert_lead(data: LeadProfile, lead_id: Optional[int] = None) -> Lead:
    """Insert or update a lead row from a LeadProfile.

    Matching priority: lead_id (when given, e.g. the agent's current chat lead);
    then email; then phone; insert only if nothing matches.
    Raises ValueError if lead_id is given but does not exist.
    Only fields explicitly sent in the request (model_fields_set) are written
    on update — defaults like channel="web" or asked_scholarship=False are
    never allowed to silently overwrite real stored values.
    Score is NOT computed here — call update_lead_score separately.
    Every write calls log_event.
    """
    db: Session = SessionLocal()
    try:
        row: Optional[LeadRow] = None

        if lead_id is not None:
            row = db.get(LeadRow, lead_id)
            if row is None:
                raise ValueError(f"Lead {lead_id} not found")

        # Match by email, then by phone
        if row is None and data.email:
            row = db.scalars(
                select(LeadRow).where(LeadRow.email == data.email)
            ).first()
        if row is None and data.phone:
            row = db.scalars(
                select(LeadRow).where(LeadRow.phone == data.phone)
            ).first()

        if row is None:
            row = LeadRow(
                name=data.name,
                phone=data.phone,
                email=data.email,
                city=data.city,
                program_interest=data.program_interest,
                twelfth_percent=data.twelfth_percent,
                entrance_exam=data.entrance_exam,
                budget_lakh=data.budget_lakh,
                asked_scholarship=data.asked_scholarship,
                channel=data.channel,
                status="new",
            )
            db.add(row)
            action = "insert"
        else:
            # Only touch fields that were explicitly provided by the caller
            sent = data.model_fields_set
            updatable = {
                "name", "phone", "email", "city", "program_interest",
                "twelfth_percent", "entrance_exam", "budget_lakh",
                "asked_scholarship", "channel",
            }
            for field in sent & updatable:
                value = getattr(data, field)
                if value is not None or field in ("asked_scholarship",):
                    setattr(row, field, value)
            action = "update"

        db.commit()
        db.refresh(row)
        result = _row_to_lead(row)
    finally:
        db.close()

    log_event(
        actor="system",
        event_type="tool_call",
        tool_name="upsert_lead",
        input=data.model_dump(),
        output={"id": result.id, "action": action, "status": result.status},
        reasoning_step=None,
        request_id=None,
        lead_id=result.id,
    )
    return result


# ---------------------------------------------------------------------------
# Public: get_lead  — stub-compatible signature
# ---------------------------------------------------------------------------

def get_lead(lead_id: int) -> Lead:
    """Fetch a lead by primary key. Raises ValueError on miss.

    Read access is also logged (access audit).
    """
    db: Session = SessionLocal()
    try:
        row = db.get(LeadRow, lead_id)
        if row is None:
            raise ValueError(f"Lead {lead_id} not found")
        result = _row_to_lead(row)
    finally:
        db.close()

    log_event(
        actor="system",
        event_type="tool_call",
        tool_name="get_lead",
        input={"lead_id": lead_id},
        output={"id": result.id, "status": result.status},
        reasoning_step=None,
        request_id=None,
        lead_id=result.id,
    )
    return result


def link_lead_to_user(lead_id: int, user_id: int) -> None:
    """Tie a lead to a student account (one lead per account)."""
    db: Session = SessionLocal()
    try:
        row = db.get(LeadRow, lead_id)
        if row is None:
            raise ValueError(f"Lead {lead_id} not found")
        row.user_id = user_id
        db.commit()
    finally:
        db.close()
    log_event(actor="system", event_type="tool_call", tool_name="link_lead_to_user",
              input={"lead_id": lead_id, "user_id": user_id}, output=None, reasoning_step=None,
              request_id=None, lead_id=lead_id)


def lead_owner(lead_id: int) -> Optional[int]:
    """The student account that owns this lead, if any."""
    db: Session = SessionLocal()
    try:
        return db.scalar(select(LeadRow.user_id).where(LeadRow.id == lead_id))
    finally:
        db.close()


# ---------------------------------------------------------------------------
# Public: request_approval  — stub-compatible signature
# ---------------------------------------------------------------------------

def request_approval(action: str, payload: dict) -> ApprovalRequest:
    """Create an approval request with status='pending'. Nothing executes.

    The approval gate must be checked (status == 'approved') before the
    action is carried out by the caller.
    """
    db: Session = SessionLocal()
    try:
        approval = Approval(
            action=action,
            payload=payload,
            status="pending",
            requested_by_actor="system",
            lead_id=payload.get("lead_id"),
        )
        db.add(approval)
        db.commit()
        db.refresh(approval)
        approval_id = approval.id
    finally:
        db.close()

    result = ApprovalRequest(
        approval_id=approval_id,
        status="pending",
        action=action,
    )

    log_event(
        actor="system",
        event_type="approval_requested",
        tool_name="request_approval",
        input={"action": action, "payload": payload},
        output={"approval_id": approval_id, "status": "pending"},
        reasoning_step=None,
        request_id=None,
        lead_id=payload.get("lead_id"),
        approval_id=approval_id,
    )
    return result


# ---------------------------------------------------------------------------
# Internal: update_lead_score
# ---------------------------------------------------------------------------

def update_lead_score(lead_id: int, score: int, tier: str) -> None:
    """Store a pre-computed score and tier on a lead row.

    Does NOT compute anything — the caller (e.g. the intel service) provides
    the values. Never imports from app.intel.
    """
    db: Session = SessionLocal()
    try:
        row = db.get(LeadRow, lead_id)
        if row is None:
            raise ValueError(f"Lead {lead_id} not found")
        row.score = score
        row.score_tier = tier
        db.commit()
    finally:
        db.close()

    log_event(
        actor="system",
        event_type="tool_call",
        tool_name="update_lead_score",
        input={"lead_id": lead_id, "score": score, "tier": tier},
        output={"ok": True},
        reasoning_step=None,
        request_id=None,
    )


# ---------------------------------------------------------------------------
# Internal: opt_out_lead  (called by router; not a stub function)
# ---------------------------------------------------------------------------

def opt_out_lead(lead_id: int) -> Lead:
    """Set opted_out=True immediately on the lead and log the action.

    Returns the updated Lead. No approval gate (opt-out is immediate by
    data-privacy convention; reversing an opt-out would require approval).
    """
    db: Session = SessionLocal()
    try:
        row = db.get(LeadRow, lead_id)
        if row is None:
            raise ValueError(f"Lead {lead_id} not found")
        row.opted_out = True
        db.commit()
        db.refresh(row)
        result = _row_to_lead(row)
    finally:
        db.close()

    log_event(
        actor="system",
        event_type="tool_call",
        tool_name="opt_out_lead",
        input={"lead_id": lead_id},
        output={"id": result.id, "opted_out": True},
        reasoning_step=None,
        request_id=None,
        lead_id=result.id,
    )
    return result


# ---------------------------------------------------------------------------
# Internal: add_interaction / list_interactions  (called by router)
# ---------------------------------------------------------------------------

def add_interaction(
    lead_id: int,
    actor: str,
    channel: str,
    direction: str,
    message: str,
    meta: Optional[dict] = None,
) -> dict:
    """Append an interaction row for a lead and log the event."""
    db: Session = SessionLocal()
    try:
        row = db.get(LeadRow, lead_id)
        if row is None:
            raise ValueError(f"Lead {lead_id} not found")
        interaction = Interaction(
            lead_id=lead_id,
            actor=actor,
            channel=channel,
            direction=direction,
            message=message,
            meta=meta,
        )
        db.add(interaction)
        db.commit()
        db.refresh(interaction)
        result = {
            "id": interaction.id,
            "lead_id": interaction.lead_id,
            "actor": interaction.actor,
            "channel": interaction.channel,
            "direction": interaction.direction,
            "message": interaction.message,
            "meta": interaction.meta,
            "created_at": interaction.created_at.isoformat(),
        }
    finally:
        db.close()

    log_event(
        actor=actor,
        event_type="tool_call",
        tool_name="add_interaction",
        input={"lead_id": lead_id, "actor": actor, "channel": channel,
               "direction": direction},
        output={"interaction_id": result["id"]},
        reasoning_step=None,
        request_id=None,
        lead_id=lead_id,
    )
    return result


def session_interactions(session_id: str) -> list[dict]:
    """Interactions recorded in one chat session, oldest first."""
    db: Session = SessionLocal()
    try:
        rows = db.scalars(
            select(Interaction)
            .where(Interaction.meta["session_id"].astext == session_id)
            .order_by(Interaction.created_at, Interaction.id)
        ).all()
        return [
            {"id": r.id, "actor": r.actor, "channel": r.channel, "direction": r.direction,
             "message": r.message, "created_at": r.created_at.isoformat()}
            for r in rows
        ]
    finally:
        db.close()


def list_interactions(lead_id: int) -> list[dict]:
    """Return all interactions for a lead, ordered by creation time."""
    db: Session = SessionLocal()
    try:
        rows = db.scalars(
            select(Interaction)
            .where(Interaction.lead_id == lead_id)
            .order_by(Interaction.created_at)
        ).all()
        return [
            {
                "id": r.id,
                "lead_id": r.lead_id,
                "actor": r.actor,
                "channel": r.channel,
                "direction": r.direction,
                "message": r.message,
                "meta": r.meta,
                "created_at": r.created_at.isoformat(),
            }
            for r in rows
        ]
    finally:
        db.close()


# ---------------------------------------------------------------------------
# Internal: list_leads  (called by router)
# ---------------------------------------------------------------------------

def list_leads(
    tier: Optional[str] = None,
    status: Optional[str] = None,
) -> list[Lead]:
    """Return leads, optionally filtered by score_tier and/or status."""
    db: Session = SessionLocal()
    try:
        stmt = select(LeadRow)
        if tier:
            stmt = stmt.where(LeadRow.score_tier == tier)
        if status:
            stmt = stmt.where(LeadRow.status == status)
        rows = db.scalars(stmt).all()
        return [_row_to_lead(r) for r in rows]
    finally:
        db.close()

