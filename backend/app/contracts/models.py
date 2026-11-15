"""Shared data shapes. Keep stubs, real services and tests in sync when these change."""
from typing import Literal, Optional
from pydantic import BaseModel


class Chunk(BaseModel):
    text: str
    source: str          # e.g. "fees_2026.md#btech-cse"
    score: float


class KnowledgeResult(BaseModel):
    answer_found: bool   # False -> agent must NOT guess, it escalates
    chunks: list[Chunk]


class LeadProfile(BaseModel):
    name: Optional[str] = None
    phone: Optional[str] = None
    email: Optional[str] = None
    city: Optional[str] = None
    state: Optional[str] = None             # Indian state or union territory
    program_interest: Optional[str] = None
    twelfth_percent: Optional[float] = None
    entrance_exam: Optional[str] = None
    budget_lakh: Optional[float] = None
    asked_scholarship: bool = False
    lateral_entry: bool = False             # joining in the second year
    channel: Literal["web", "whatsapp", "email"] = "web"


class LeadScore(BaseModel):
    score: int                              # 0-100
    tier: Literal["hot", "warm", "cold"]
    reasons: list[str]                      # shown in the UI, keeps scoring explainable


class Lead(BaseModel):
    id: int
    profile: LeadProfile
    score: Optional[LeadScore] = None
    status: str = "new"
    opted_out: bool = False
    contact_consent: bool = False           # set only by registration; deliberately not in LeadProfile
    consent_at: Optional[str] = None        # ISO time the consent was given


class Slot(BaseModel):
    slot_id: str
    counsellor: str
    start: str           # ISO datetime
    end: str


class BookingResult(BaseModel):
    ok: bool
    slot: Optional[Slot] = None
    reason: Optional[str] = None            # e.g. "slot_taken"
    alternatives: list[Slot] = []


class CounsellorInfo(BaseModel):
    name: str
    next_free: Optional[str] = None         # ISO start of their next free session, if any this week


class CancelResult(BaseModel):
    ok: bool
    slot: Optional[Slot] = None             # the session that was released
    reason: Optional[str] = None            # "no_booking" | "lead_not_found"


class MessageResult(BaseModel):
    ok: bool
    message_id: Optional[str] = None
    error: Optional[str] = None


class ApprovalRequest(BaseModel):
    approval_id: int
    status: Literal["pending", "approved", "rejected"]
    action: str
