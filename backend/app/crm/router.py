# Owner: Dev. DB schema, mock CRM, auth/RBAC, approvals, audit log.
# Real functions go in app/crm/service.py with the same signatures as contracts/stubs.py.
from typing import Literal, Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.contracts.models import ApprovalRequest, Lead, LeadProfile
from app.crm import service
from app.crm.db.base import get_session

router = APIRouter()


# ---------------------------------------------------------------------------
# Request / response schemas (local — no contracts change)
# ---------------------------------------------------------------------------

class InteractionIn(BaseModel):
    actor: Literal["agent", "counsellor", "system"]
    channel: Literal["web", "whatsapp", "email"]
    direction: Literal["inbound", "outbound"]
    message: str
    meta: Optional[dict] = None


# ---------------------------------------------------------------------------
# Health (existing)
# ---------------------------------------------------------------------------

@router.get("/health")
def health():
    return {"module": "crm", "ok": True}


# ---------------------------------------------------------------------------
# Leads
# ---------------------------------------------------------------------------

@router.post("/leads", response_model=Lead, status_code=201)
def create_lead(data: LeadProfile):
    """Upsert a lead from a LeadProfile. Matches on email when present."""
    return service.upsert_lead(data)


@router.get("/leads", response_model=list[Lead])
def list_leads(
    tier: Optional[str] = None,
    status: Optional[str] = None,
):
    """Return all leads, optionally filtered by tier and/or status."""
    return service.list_leads(tier=tier, status=status)


@router.get("/leads/{lead_id}", response_model=Lead)
def read_lead(lead_id: int):
    """Fetch a single lead by ID. Returns 404 if not found."""
    try:
        return service.get_lead(lead_id)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc))


# ---------------------------------------------------------------------------
# Interactions
# ---------------------------------------------------------------------------

@router.post("/leads/{lead_id}/interactions", status_code=201)
def add_interaction(lead_id: int, body: InteractionIn):
    """Append a new interaction for a lead."""
    try:
        return service.add_interaction(
            lead_id=lead_id,
            actor=body.actor,
            channel=body.channel,
            direction=body.direction,
            message=body.message,
            meta=body.meta,
        )
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc))


@router.get("/leads/{lead_id}/interactions")
def list_interactions(lead_id: int):
    """Return all interactions for a lead, oldest first."""
    try:
        # Verify lead exists before listing
        service.get_lead(lead_id)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc))
    return service.list_interactions(lead_id)


# ---------------------------------------------------------------------------
# Opt-out  (applies immediately; reversing requires approval — not this endpoint)
# ---------------------------------------------------------------------------

@router.patch("/leads/{lead_id}/opt-out", response_model=Lead)
def opt_out_lead(lead_id: int):
    """Set opted_out=True on the lead immediately and return the updated lead.

    Opt-out is applied without an approval gate (privacy-first).
    Reversing an opt-out is a state change that requires an ApprovalRequest.
    """
    try:
        return service.opt_out_lead(lead_id)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc))
