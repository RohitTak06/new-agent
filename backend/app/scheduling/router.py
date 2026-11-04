"""Scheduling and channels API (SPEC section 4). Roles enforced on every route."""
from typing import Literal, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from pydantic import BaseModel, Field

from app.contracts.models import BookingResult, Slot
from app.crm.auth import (CurrentUser, audit_action, current_user, ensure_lead_access, require_lead_access,
                          require_staff)
from app.scheduling import clock, followups, service

router = APIRouter()


class BookRequest(BaseModel):
    lead_id: int
    slot_id: str


class FollowupRequest(BaseModel):
    lead_id: int
    when: str = Field(description="ISO datetime; naive values are IST")
    template: str = Field(min_length=1, max_length=2000)


class AdvanceRequest(BaseModel):
    hours: float = Field(gt=0, le=clock.MAX_ADVANCE_HOURS)


@router.get("/health")
def health():
    return {"module": "scheduling", "ok": True}


@router.get("/slots", response_model=list[Slot], dependencies=[Depends(current_user)])
def get_slots(date_from: str, date_to: str):
    """Free future slots between two IST dates/datetimes (date_to inclusive)."""
    try:
        return service.get_slots(date_from, date_to)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc))


@router.post("/book", response_model=BookingResult)
def book(req: BookRequest, request: Request, user: CurrentUser = Depends(current_user)):
    """Book a slot (students: only for their own lead). A clash returns 200 with ok=false and alternatives."""
    ensure_lead_access(user, req.lead_id, request)
    result = service.book_slot(req.lead_id, req.slot_id)
    audit_action(user, "book_slot", req.model_dump(), {"ok": result.ok, "reason": result.reason},
                 None if result.reason == "lead_not_found" else req.lead_id)
    return result


@router.get("/messages/{lead_id}", dependencies=[Depends(require_lead_access)])
def messages(lead_id: int):
    return service.list_messages(lead_id)


@router.post("/followups")
def create_followup(req: FollowupRequest, user: CurrentUser = Depends(require_staff)):
    result = service.schedule_followup(req.lead_id, req.when, req.template)
    audit_action(user, "schedule_followup", req.model_dump(), result, req.lead_id if result["ok"] else None)
    if not result["ok"]:
        raise HTTPException(status_code=404 if result["error"] == "lead_not_found" else 422, detail=result)
    return result


@router.get("/followups", dependencies=[Depends(require_staff)])
def list_followups(lead_id: Optional[int] = None,
                   status: Optional[Literal["pending", "sent", "skipped", "failed"]] = Query(default=None)):
    return service.list_followups(lead_id, status)


@router.get("/clock", dependencies=[Depends(require_staff)])
def get_clock():
    now = clock.now()
    return {"now": clock.to_ist(now), "offset_hours": round(clock.offset_seconds() / 3600, 2)}


@router.post("/clock/advance")
def advance_clock(req: AdvanceRequest, user: CurrentUser = Depends(require_staff)):
    """Fast-forward the virtual clock, then send anything now due (the demo's fast-forward button)."""
    before = clock.to_ist(clock.now())
    now = clock.advance(req.hours)
    audit_action(user, "clock_advance", {"hours": req.hours}, {"from": before, "to": clock.to_ist(now)})
    dispatched = followups.dispatch_due()
    return {"now": clock.to_ist(now), "offset_hours": round(clock.offset_seconds() / 3600, 2),
            "followups": dispatched}
