"""CRM API: auth, leads, interactions, approvals, audit and analytics. Roles enforced on every route."""
from datetime import datetime
from typing import Literal, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from fastapi.security import OAuth2PasswordRequestForm
from pydantic import BaseModel, Field

from app.contracts.models import Lead, LeadProfile
from app.crm import approvals, auth, reports, service
from app.crm.auth import CurrentUser, audit_action, current_user, require_lead_access, require_staff

router = APIRouter()


class TokenOut(BaseModel):
    access_token: str
    token_type: str = "bearer"
    role: str


class InteractionIn(BaseModel):
    channel: Literal["web", "whatsapp", "email"]
    direction: Literal["inbound", "outbound"]
    message: str = Field(min_length=1, max_length=5000)
    meta: Optional[dict] = None


class ApproveIn(BaseModel):
    note: Optional[str] = Field(default=None, max_length=2000)
    reply: Optional[str] = Field(default=None, max_length=2000, description="Counsellor's message to the student")


class RejectIn(BaseModel):
    reason: str = Field(min_length=1, max_length=2000)


@router.get("/health")
def health():
    return {"module": "crm", "ok": True}


# ---------------------------------------------------------------------------
# Auth
# ---------------------------------------------------------------------------

@router.post("/auth/login", response_model=TokenOut)
def login(form: OAuth2PasswordRequestForm = Depends()):
    """Exchange email (form field `username`) and password for a bearer token."""
    user = auth.authenticate(form.username, form.password)
    if user is None:
        raise HTTPException(status_code=401, detail="Incorrect email or password",
                            headers={"WWW-Authenticate": "Bearer"})
    return TokenOut(access_token=auth.create_token(user.id, user.role), role=user.role)


@router.get("/auth/me", response_model=CurrentUser)
def me(user: CurrentUser = Depends(current_user)):
    return user


# ---------------------------------------------------------------------------
# Leads
# ---------------------------------------------------------------------------

@router.post("/leads", response_model=Lead, status_code=201)
def create_lead(data: LeadProfile, user: CurrentUser = Depends(require_staff)):
    """Upsert a lead from a LeadProfile. Matches on email when present."""
    lead = service.upsert_lead(data)
    audit_action(user, "create_lead", data.model_dump(), {"id": lead.id}, lead.id)
    return lead


@router.get("/leads", response_model=list[Lead], dependencies=[Depends(require_staff)])
def list_leads(tier: Optional[str] = None, status: Optional[str] = None):
    """Return all leads, optionally filtered by tier and/or status."""
    return service.list_leads(tier=tier, status=status)


@router.get("/leads/{lead_id}", response_model=Lead, dependencies=[Depends(require_lead_access)])
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
def add_interaction(lead_id: int, body: InteractionIn, user: CurrentUser = Depends(require_staff)):
    """Append an interaction for a lead. The actor comes from the token, not the request."""
    try:
        result = service.add_interaction(lead_id=lead_id, actor="counsellor", channel=body.channel,
                                         direction=body.direction, message=body.message, meta=body.meta)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc))
    audit_action(user, "add_interaction", {"direction": body.direction}, {"id": result["id"]}, lead_id)
    return result


@router.get("/leads/{lead_id}/interactions", dependencies=[Depends(require_lead_access)])
def list_interactions(lead_id: int):
    """Return all interactions for a lead, oldest first."""
    try:
        service.get_lead(lead_id)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc))
    return service.list_interactions(lead_id)


# ---------------------------------------------------------------------------
# Opt-out  (applies immediately; reversing requires approval — not this endpoint)
# ---------------------------------------------------------------------------

@router.patch("/leads/{lead_id}/opt-out", response_model=Lead)
def opt_out_lead(lead_id: int, user: CurrentUser = Depends(require_lead_access)):
    """Set opted_out=True immediately (privacy-first, no approval gate). Students may opt themselves out."""
    try:
        lead = service.opt_out_lead(lead_id)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc))
    audit_action(user, "opt_out", None, {"opted_out": True}, lead_id)
    return lead


# ---------------------------------------------------------------------------
# Approvals
# ---------------------------------------------------------------------------

@router.get("/approvals", dependencies=[Depends(require_staff)])
def list_approvals(status: Optional[Literal["pending", "approved", "rejected"]] = None):
    return approvals.list_approvals(status)


@router.post("/approvals/{approval_id}/approve")
def approve(approval_id: int, body: ApproveIn, user: CurrentUser = Depends(require_staff)):
    """Approve and run the action. 409 if already resolved; 422 if it can't run (it stays pending)."""
    try:
        return approvals.approve(approval_id, user, note=body.note, reply=body.reply)
    except approvals.ApprovalError as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.detail)


@router.post("/approvals/{approval_id}/reject")
def reject(approval_id: int, body: RejectIn, user: CurrentUser = Depends(require_staff)):
    """Reject without running the action; the student is told the reason and offered a call."""
    try:
        return approvals.reject(approval_id, user, body.reason)
    except approvals.ApprovalError as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.detail)


# ---------------------------------------------------------------------------
# Audit and analytics
# ---------------------------------------------------------------------------

@router.get("/audit", dependencies=[Depends(require_staff)])
def audit(lead_id: Optional[int] = None, session_id: Optional[str] = None,
          event_type: Optional[str] = Query(default=None, alias="type"),
          date_from: Optional[datetime] = Query(default=None, alias="from"),
          date_to: Optional[datetime] = Query(default=None, alias="to"),
          limit: int = Query(default=100, ge=1, le=reports.MAX_AUDIT_ROWS),
          offset: int = Query(default=0, ge=0)):
    """Read the append-only audit trail, newest first."""
    return reports.list_audit(lead_id, session_id, event_type, date_from, date_to, limit, offset)


@router.get("/analytics/funnel", dependencies=[Depends(require_staff)])
def funnel():
    return reports.funnel()
