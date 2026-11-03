"""Hardcoded fake implementations so everyone can build in parallel.
Real versions live in each module's service.py with the SAME signatures."""
from app.contracts.models import (
    ApprovalRequest, BookingResult, Chunk, KnowledgeResult, Lead, LeadProfile,
    LeadScore, MessageResult, Slot,
)

_SLOTS = [
    Slot(slot_id="s1", counsellor="Dr. Sharma", start="2026-11-03T10:00:00", end="2026-11-03T10:30:00"),
    Slot(slot_id="s2", counsellor="Dr. Sharma", start="2026-11-03T11:00:00", end="2026-11-03T11:30:00"),
    Slot(slot_id="s3", counsellor="Ms. Verma", start="2026-11-04T15:00:00", end="2026-11-04T15:30:00"),
]


# ---- Guru: intel ----
def search_knowledge(query: str) -> KnowledgeResult:
    if "hostel" in query.lower():
        return KnowledgeResult(answer_found=False, chunks=[])
    return KnowledgeResult(
        answer_found=True,
        chunks=[Chunk(text="B.Tech CSE annual tuition is a placeholder amount.", source="stub_fees.md#cse", score=0.9)],
    )


def score_lead(profile: LeadProfile) -> LeadScore:
    return LeadScore(score=72, tier="warm", reasons=["stub: program interest given", "stub: no booking yet"])


# ---- Dev: crm ----
def upsert_lead(data: LeadProfile, lead_id: int | None = None) -> Lead:
    return Lead(id=lead_id or 1, profile=data, status="new")


def get_lead(lead_id: int) -> Lead:
    return Lead(id=lead_id, profile=LeadProfile(name="Stub Student"), status="new")


def request_approval(action: str, payload: dict) -> ApprovalRequest:
    return ApprovalRequest(approval_id=1, status="pending", action=action)


# ---- Riya: scheduling ----
def get_slots(date_from: str, date_to: str) -> list[Slot]:
    return _SLOTS


def book_slot(lead_id: int, slot_id: str) -> BookingResult:
    if slot_id == "s1":  # simulate a clash so the agent can practise alternatives
        return BookingResult(ok=False, reason="slot_taken", alternatives=_SLOTS[1:])
    chosen = next((s for s in _SLOTS if s.slot_id == slot_id), None)
    return BookingResult(ok=chosen is not None, slot=chosen)


def send_message(channel: str, lead_id: int, text: str) -> MessageResult:
    return MessageResult(ok=True, message_id="stub-msg-1")


def schedule_followup(lead_id: int, when: str, template: str) -> dict:
    return {"ok": True, "followup_id": 1, "when": when, "template": template}
