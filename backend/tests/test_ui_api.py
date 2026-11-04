"""The small API surface the frontend screens rely on (Phase 5)."""
import json
import uuid

import pytest
from fastapi.testclient import TestClient

from app.agent import router as agent_router
from app.contracts import tools
from app.contracts.models import LeadProfile
from app.crm import service as crm
from app.main import app
from app.scheduling import faults, seed
from app.scheduling import service as sched
from fakes import FakeLLM, calls, says

CHIT = {"intent": "chitchat", "needs_clarification": False, "clarifying_question": None, "steps": []}


@pytest.fixture
def client():
    return TestClient(app)


@pytest.fixture(scope="module", autouse=True)
def slots():
    seed.seed_slots()


@pytest.fixture(autouse=True)
def clear_faults():
    yield
    for target in faults.TARGETS:
        faults.arm(target, 0)


def new_lead(**profile) -> int:
    tag = uuid.uuid4().hex[:8]
    return crm.upsert_lead(LeadProfile(**{"name": f"Test {tag}", "email": f"{tag}@example.test", **profile})).id


def free_slot() -> str:
    return sched.get_slots("2020-01-01", "2099-12-31")[0].slot_id


def post_chat(client, monkeypatch, message, reply="Happy to help.", headers=None, **body):
    monkeypatch.setattr(agent_router, "get_llm", lambda: FakeLLM(CHIT, [says(reply)]))
    res = client.post("/agent/chat", json={"message": message, **body}, headers=headers)
    assert res.status_code == 200, res.text
    return [json.loads(line[6:]) for line in res.text.splitlines() if line.startswith("data: ")]


# ---------------------------------------------------------------- opted_out in the contract
def test_lead_shows_opted_out(client, users):
    lead = new_lead()
    url = f"/crm/leads/{lead}"
    assert client.get(url, headers=users.counsellor.headers).json()["opted_out"] is False
    crm.opt_out_lead(lead)
    assert client.get(url, headers=users.counsellor.headers).json()["opted_out"] is True


# ---------------------------------------------------------------- bookings
def test_staff_see_every_booking_with_the_lead_name(client, users):
    lead = new_lead(name="Booked Lead")
    assert sched.book_slot(lead, free_slot()).ok
    rows = client.get("/scheduling/bookings", headers=users.counsellor.headers).json()
    row = next(r for r in rows if r["lead_id"] == lead)
    assert row["lead_name"] == "Booked Lead" and row["counsellor"] and row["upcoming"] is True


def test_booking_filter_returns_one_lead(client, users):
    lead, other = new_lead(), new_lead()
    assert sched.book_slot(lead, free_slot()).ok
    assert sched.book_slot(other, free_slot()).ok
    rows = client.get("/scheduling/bookings", params={"lead_id": lead}, headers=users.counsellor.headers).json()
    assert {r["lead_id"] for r in rows} == {lead}


def test_student_sees_only_their_own_bookings(client, users):
    student = users.student
    other = new_lead()
    assert sched.book_slot(other, free_slot()).ok
    assert sched.book_slot(student.lead_id, free_slot()).ok
    mine = client.get("/scheduling/bookings", headers=student.headers).json()
    assert mine and {r["lead_id"] for r in mine} == {student.lead_id}
    assert client.get("/scheduling/bookings", params={"lead_id": other}, headers=student.headers).status_code == 403


# ---------------------------------------------------------------- approvals by lead
def test_approvals_filter_by_lead(client, users):
    lead, other = new_lead(), new_lead()
    mine = tools.request_fee_waiver(lead, "hardship").approval_id
    tools.request_fee_waiver(other, "hardship")
    rows = client.get("/crm/approvals", params={"lead_id": lead}, headers=users.counsellor.headers).json()
    assert [r["id"] for r in rows] == [mine]


# ---------------------------------------------------------------- failure demo status
def test_fault_status_is_admin_only_and_reports_what_is_armed(client, users, monkeypatch):
    assert client.get("/scheduling/faults", headers=users.counsellor.headers).status_code == 403
    monkeypatch.setenv("ENABLE_FAULT_INJECTION", "1")
    faults.arm("book_slot", 2)
    body = client.get("/scheduling/faults", headers=users.admin.headers).json()
    assert body["enabled"] is True and body["remaining"]["book_slot"] == 2
    monkeypatch.setenv("ENABLE_FAULT_INJECTION", "0")
    assert client.get("/scheduling/faults", headers=users.admin.headers).json()["enabled"] is False


# ---------------------------------------------------------------- channel conversations
def test_whatsapp_chat_is_stored_as_messages_both_ways(client, monkeypatch):
    final = post_chat(client, monkeypatch, "Hello from my phone", channel="whatsapp")[-1]["data"]
    rows = sched.list_messages(final["lead_id"])
    assert [(m["channel"], m["direction"], m["text"]) for m in rows] == [
        ("whatsapp", "inbound", "Hello from my phone"), ("whatsapp", "outbound", "Happy to help.")]
    assert rows[1]["meta"]["session_id"] == final["session_id"]


def test_web_chat_adds_no_messages(client, monkeypatch):
    final = post_chat(client, monkeypatch, "Hello from the website")[-1]["data"]
    assert sched.list_messages(final["lead_id"]) == []


def test_opted_out_student_writing_in_still_sees_the_conversation(client, monkeypatch):
    lead = post_chat(client, monkeypatch, "Hi", channel="whatsapp")[-1]["data"]["lead_id"]
    crm.opt_out_lead(lead)
    assert sched.send_message("whatsapp", lead, "Campaign").error == "opted_out"
    assert len(sched.list_messages(lead)) == 2


def test_channel_messages_are_audited(client, monkeypatch, users):
    lead = post_chat(client, monkeypatch, "Hi", channel="email")[-1]["data"]["lead_id"]
    rows = client.get("/crm/audit", params={"lead_id": lead, "type": "channel_message"},
                      headers=users.admin.headers).json()
    assert {r["input"]["direction"] for r in rows} == {"inbound", "outbound"}


# ---------------------------------------------------------------- "Book this" and spoken slot ids
@pytest.mark.parametrize("spoken", ["{}", "slot_{}", "slot {}", "Slot-{}"])
def test_book_slot_accepts_the_id_however_the_model_echoes_it(client, monkeypatch, spoken):
    slot = free_slot()
    plan = {**CHIT, "intent": "booking"}
    llm = FakeLLM(plan, [calls(("book_slot", {"slot_id": spoken.format(slot)})), says("Your session is booked.")])
    monkeypatch.setattr(agent_router, "get_llm", lambda: llm)
    res = client.post("/agent/chat", json={"message": f"Please book slot {slot}"})
    events = [json.loads(line[6:]) for line in res.text.splitlines() if line.startswith("data: ")]
    result = next(e["data"]["result"] for e in events if e["type"] == "tool_result" and e["data"]["name"] == "book_slot")
    assert result["ok"] and result["slot"]["slot_id"] == slot
