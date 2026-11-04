"""Shared data shapes. Change only via a PR that all 4 approve."""
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
    program_interest: Optional[str] = None
    twelfth_percent: Optional[float] = None
    entrance_exam: Optional[str] = None
    budget_lakh: Optional[float] = None
    asked_scholarship: bool = False
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


class MessageResult(BaseModel):
    ok: bool
    message_id: Optional[str] = None
    error: Optional[str] = None


class ApprovalRequest(BaseModel):
    approval_id: int
    status: Literal["pending", "approved", "rejected"]
    action: str
