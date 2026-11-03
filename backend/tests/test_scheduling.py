"""Scheduling: atomic booking, alternatives, virtual clock, follow-ups (SPEC S4, S6, S9 at service level)."""
import inspect
import threading
import uuid
from concurrent.futures import ThreadPoolExecutor
from datetime import timedelta

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select, update

from app.contracts import stubs
from app.contracts.models import LeadProfile
from app.crm import service as crm
from app.crm.db.base import SessionLocal
from app.crm.db.models import AuditLog
from app.main import app
from app.scheduling import clock, followups, service
from app.scheduling.models import FollowupRow, MessageRow, SlotRow, VirtualClock
from app.scheduling.seed import seed_slots


@pytest.fixture(scope="module", autouse=True)
def slots():
    seed_slots()


@pytest.fixture
def restore_clock():
    """Tests may fast-forward; put the clock back so later tests see the same 'now'."""
    before = clock.offset_seconds()
    yield
    with SessionLocal() as db:
        db.execute(update(VirtualClock).where(VirtualClock.id == 1).values(offset_seconds=before))
        db.commit()


def new_lead(**profile) -> int:
    tag = uuid.uuid4().hex[:8]
    data = {"name": f"Test {tag}", "email": f"{tag}@example.test", **profile}
    return crm.upsert_lead(LeadProfile(**data)).id


def free_slots(n=10):
    now = clock.now().astimezone(clock.IST)
    return service.get_slots(now.date().isoformat(), (now + timedelta(days=7)).date().isoformat())[:n]


def slot_row(slot_id: str) -> SlotRow:
    with SessionLocal() as db:
        return db.get(SlotRow, int(slot_id))


# ------------------------------------------------------------------ contract
@pytest.mark.parametrize("name", ["get_slots", "book_slot", "send_message", "schedule_followup"])
def test_real_service_matches_stub_signature(name):
    stub, real = inspect.signature(getattr(stubs, name)), inspect.signature(getattr(service, name))
    assert [(p.name, p.default) for p in stub.parameters.values()] == \
           [(p.name, p.default) for p in real.parameters.values()]


# ------------------------------------------------------------------ slots
def test_get_slots_are_free_future_and_ordered():
    got = free_slots(50)
    assert got, "seed should create slots"
    starts = [clock.parse(s.start) for s in got]
    assert starts == sorted(starts) and all(t > clock.now() for t in starts)
    assert all(slot_row(s.slot_id).status == "free" for s in got)
    assert got[0].start.endswith("+05:30")


# ------------------------------------------------------------------ S4 booking
def test_concurrent_booking_of_one_slot_gives_exactly_one_winner():
    slot = free_slots(1)[0]
    leads = [new_lead() for _ in range(10)]
    barrier = threading.Barrier(len(leads))

    def attempt(lead_id):
        barrier.wait()
        return lead_id, service.book_slot(lead_id, slot.slot_id)

    with ThreadPoolExecutor(max_workers=len(leads)) as pool:
        results = list(pool.map(attempt, leads))

    winners = [lead for lead, r in results if r.ok]
    losers = [r for _, r in results if not r.ok]
    assert len(winners) == 1 and len(losers) == 9
    assert all(r.reason == "slot_taken" and len(r.alternatives) == 3 for r in losers)
    row = slot_row(slot.slot_id)
    assert row.status == "booked" and row.lead_id == winners[0]
    with SessionLocal() as db:
        assert len(db.scalars(select(SlotRow).where(SlotRow.lead_id.in_(leads))).all()) == 1


def test_alternatives_are_nearest_free_future_slots():
    slot = free_slots(1)[0]
    service.book_slot(new_lead(), slot.slot_id)
    res = service.book_slot(new_lead(), slot.slot_id)
    assert not res.ok and res.reason == "slot_taken"
    target = clock.parse(slot.start)
    alt_gaps = [abs(clock.parse(a.start) - target) for a in res.alternatives]
    all_gaps = sorted(abs(clock.parse(s.start) - target) for s in free_slots(50) if s.slot_id != slot.slot_id)
    assert alt_gaps == all_gaps[:3]
    assert all(slot_row(a.slot_id).status == "free" and clock.parse(a.start) > clock.now() for a in res.alternatives)


def test_one_lead_cannot_hold_two_upcoming_bookings_even_concurrently():
    lead = new_lead()
    candidates = free_slots(5)
    barrier = threading.Barrier(len(candidates))

    def attempt(slot):
        barrier.wait()
        return service.book_slot(lead, slot.slot_id)

    with ThreadPoolExecutor(max_workers=len(candidates)) as pool:
        results = list(pool.map(attempt, candidates))
    assert sum(r.ok for r in results) == 1
    assert {r.reason for r in results if not r.ok} == {"already_booked"}


def test_rebooking_own_slot_is_idempotent():
    lead, slot = new_lead(), free_slots(1)[0]
    first, again = service.book_slot(lead, slot.slot_id), service.book_slot(lead, slot.slot_id)
    assert first.ok and again.ok and again.slot.slot_id == slot.slot_id


def test_unknown_and_past_slots_are_refused(restore_clock):
    assert service.book_slot(new_lead(), "999999").reason == "slot_not_found"
    assert service.book_slot(new_lead(), "abc").reason == "slot_not_found"
    slot = free_slots(1)[0]
    clock.advance((clock.parse(slot.end) - clock.now()).total_seconds() / 3600 + 0.1)
    res = service.book_slot(new_lead(), slot.slot_id)
    assert not res.ok and res.reason == "slot_in_past"


# ------------------------------------------------------------------ messages
def test_send_message_stores_mock_message_and_audits():
    lead = new_lead()
    res = service.send_message("whatsapp", lead, "Hello from JKLU")
    assert res.ok and res.message_id
    msgs = service.list_messages(lead)
    assert [(m["channel"], m["direction"], m["text"]) for m in msgs] == [("whatsapp", "outbound", "Hello from JKLU")]
    assert service.send_message("sms", lead, "hi").error == "invalid_channel"


def test_opted_out_lead_gets_no_messages_or_new_followups():
    lead = new_lead()
    crm.opt_out_lead(lead)
    assert service.send_message("email", lead, "hi").error == "opted_out"
    assert service.schedule_followup(lead, clock.to_ist(clock.now()), "hot_reminder")["error"] == "opted_out"
    assert service.list_messages(lead) == []


# ------------------------------------------------------------------ S6 follow-ups
def _due_in_24h() -> str:
    return clock.to_ist(clock.now() + timedelta(hours=24))


def test_s6_due_followup_fires_after_clock_advance(restore_clock):
    lead = new_lead(name="Aarav Test", program_interest="B.Tech CSE")
    crm.update_lead_score(lead, 88, "hot")
    f = service.schedule_followup(lead, _due_in_24h(), "hot_reminder")
    assert f["ok"]

    assert f["followup_id"] not in [o["followup_id"] for o in followups.dispatch_due()["processed"]]
    res = TestClient(app).post("/scheduling/clock/advance", json={"hours": 24})
    assert res.status_code == 200
    outcome = next(o for o in res.json()["followups"]["processed"] if o["followup_id"] == f["followup_id"])
    assert outcome["status"] == "sent" and outcome["detail"] == "email"

    [msg] = service.list_messages(lead)
    assert msg["channel"] == "email" and "Aarav Test" in msg["text"] and "B.Tech CSE" in msg["text"]
    assert msg["meta"]["followup_id"] == f["followup_id"]
    with SessionLocal() as db:
        assert db.get(FollowupRow, f["followup_id"]).status == "sent"
        audit = db.scalars(select(AuditLog).where(AuditLog.event_type == "followup",
                                                  AuditLog.lead_id == lead)).all()
    assert len(audit) == 1 and audit[0].output["status"] == "sent"

    assert f["followup_id"] not in [o["followup_id"] for o in followups.dispatch_due()["processed"]]
    assert len(service.list_messages(lead)) == 1


def test_followup_skipped_when_lead_opts_out_after_scheduling(restore_clock):
    lead = new_lead()
    f = service.schedule_followup(lead, _due_in_24h(), "warm_nudge")
    crm.opt_out_lead(lead)
    clock.advance(25)
    outcome = next(o for o in followups.dispatch_due()["processed"] if o["followup_id"] == f["followup_id"])
    assert outcome["status"] == "skipped" and outcome["detail"] == "opted_out"
    assert service.list_messages(lead) == []


def test_followup_skipped_when_lead_replied(restore_clock):
    lead = new_lead()
    f = service.schedule_followup(lead, _due_in_24h(), "hot_reminder")
    crm.add_interaction(lead, actor="student", channel="web", direction="inbound", message="Yes, call me")
    clock.advance(25)
    outcome = next(o for o in followups.dispatch_due()["processed"] if o["followup_id"] == f["followup_id"])
    assert outcome["status"] == "skipped" and outcome["detail"] == "lead_replied"


def test_concurrent_dispatch_sends_once(restore_clock):
    lead = new_lead()
    f = service.schedule_followup(lead, _due_in_24h(), "cold_nurture")
    clock.advance(25)
    with ThreadPoolExecutor(max_workers=4) as pool:
        runs = list(pool.map(lambda _: followups.dispatch_due(), range(4)))
    hits = [o for r in runs for o in r["processed"] if o["followup_id"] == f["followup_id"]]
    assert len(hits) == 1 and len(service.list_messages(lead)) == 1


# ------------------------------------------------------------------ endpoints
def test_endpoints_book_clash_and_clock_validation(restore_clock):
    client = TestClient(app)
    slot = free_slots(1)[0]
    a, b = new_lead(), new_lead()
    assert client.post("/scheduling/book", json={"lead_id": a, "slot_id": slot.slot_id}).json()["ok"] is True
    clash = client.post("/scheduling/book", json={"lead_id": b, "slot_id": slot.slot_id}).json()
    assert clash["ok"] is False and clash["reason"] == "slot_taken" and len(clash["alternatives"]) == 3
    assert client.post("/scheduling/clock/advance", json={"hours": 0}).status_code == 422
    assert client.post("/scheduling/followups", json={"lead_id": 999999, "when": _due_in_24h(),
                                                      "template": "hot_reminder"}).status_code == 404
    assert client.get("/scheduling/clock").json()["now"].endswith("+05:30")
