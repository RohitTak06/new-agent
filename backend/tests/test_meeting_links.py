"""Simulated meeting links: issued with each booking, sent to the student, shown to staff, checked in replies."""
import json
import re
import uuid
from datetime import timedelta

import pytest
from fastapi.testclient import TestClient

from app.agent import router as agent_router
from app.agent.verify import TurnEvidence, check_booking
from app.contracts.models import BookingResult, LeadProfile, Slot
from app.crm import service as crm
from app.main import app
from app.scheduling import clock
from app.scheduling import service as sched
from app.scheduling.seed import seed_slots
from fakes import FakeLLM, calls, says
from students import headers_for, remember

LINK = re.compile(r"^https://meet\.jklu\.example/[a-z]{3}-[a-z]{4}-[a-z]{3}$")


@pytest.fixture(scope="module", autouse=True)
def slots():
    seed_slots()


@pytest.fixture
def client():
    return TestClient(app)


def new_lead(**profile) -> int:
    tag = uuid.uuid4().hex[:8]
    return crm.upsert_lead(LeadProfile(**{"name": f"Test {tag}", "email": f"{tag}@example.test", **profile})).id


def free(n: int = 2) -> list[Slot]:
    now = clock.now().astimezone(clock.IST)
    return sched.get_slots(now.date().isoformat(), (now + timedelta(days=7)).date().isoformat())[:n]


# ---------------------------------------------------------------- issuing
def test_each_booking_gets_its_own_link():
    a, b = free(2)
    first, second = sched.book_slot(new_lead(), a.slot_id), sched.book_slot(new_lead(), b.slot_id)
    assert LINK.match(first.slot.meeting_url) and LINK.match(second.slot.meeting_url)
    assert first.slot.meeting_url != second.slot.meeting_url


def test_a_free_slot_has_no_link():
    assert all(s.meeting_url is None for s in free(20))


def test_booking_again_keeps_the_same_link_and_sends_nothing_new():
    lead, slot = new_lead(), free(1)[0]
    first = sched.book_slot(lead, slot.slot_id)
    again = sched.book_slot(lead, slot.slot_id)
    assert again.ok and again.slot.meeting_url == first.slot.meeting_url
    assert len(sched.list_messages(lead)) == 1


def test_staff_and_student_see_the_link_on_the_booking(client, users):
    slot = free(1)[0]
    lead = new_lead()
    url = sched.book_slot(lead, slot.slot_id).slot.meeting_url
    staff = client.get("/scheduling/bookings", params={"lead_id": lead}, headers=users.counsellor.headers).json()
    assert staff[0]["meeting_url"] == url


# ---------------------------------------------------------------- telling the student
def test_the_student_is_sent_the_link_on_their_own_channel():
    lead, slot = new_lead(), free(1)[0]
    url = sched.book_slot(lead, slot.slot_id).slot.meeting_url
    [msg] = sched.list_messages(lead)
    assert msg["channel"] == "email" and url in msg["text"] and "simulated" in msg["text"]


def test_an_opted_out_student_still_books_but_gets_no_message():
    lead, slot = new_lead(), free(1)[0]
    crm.opt_out_lead(lead)
    assert sched.book_slot(lead, slot.slot_id).ok
    assert sched.list_messages(lead) == []


def test_cancelling_removes_the_link_and_says_so():
    lead, slot = new_lead(), free(1)[0]
    url = sched.book_slot(lead, slot.slot_id).slot.meeting_url
    res = sched.cancel_booking(lead)
    assert res.ok and res.slot.meeting_url == url                     # the student is told which one ended
    assert all(s.meeting_url is None for s in free(50) if s.slot_id == slot.slot_id)
    assert "cancelled" in sched.list_messages(lead)[-1]["text"]


# ---------------------------------------------------------------- the check on replies
SLOT = Slot(slot_id="9", counsellor="Ms. Rekha Verma", start="2026-11-16T11:00:00+05:30",
            end="2026-11-16T11:30:00+05:30", meeting_url="https://meet.jklu.example/abc-defg-hij")


def booked() -> TurnEvidence:
    return TurnEvidence(bookings=[BookingResult(ok=True, slot=SLOT)])


def test_a_link_the_calendar_issued_passes():
    assert check_booking(f"You're booked. Join here: {SLOT.meeting_url}.", booked()).ok


@pytest.mark.parametrize("link", ["https://meet.jklu.example/zzz-zzzz-zzz", "https://meet.google.com/abc-defg-hij",
                                  "https://us02web.zoom.us/j/123", "https://meet.jit.si/JKLU-room"])
def test_a_link_the_model_wrote_is_caught(link):
    v = check_booking(f"You're booked. Join here: {link}", booked())
    assert not v.ok and v.action == "replan" and v.details["links"] == [link]


def test_the_link_of_a_session_held_before_this_turn_passes():
    evidence = TurnEvidence(meeting_urls={SLOT.meeting_url})
    assert check_booking(f"Your session link is {SLOT.meeting_url}", evidence).ok


# ---------------------------------------------------------------- through the agent
def test_the_agent_hands_over_the_issued_link(client, monkeypatch):
    slot = free(1)[0]

    def reply(convo):
        result = next(r for name, r, _ in llm.tool_results if name == "book_slot")
        return says(f"You're booked with {result['slot']['counsellor']}. Join here: {result['slot']['meeting_url']} "
                    "(a simulated link). It was also sent to you by email.")

    llm = FakeLLM({"intent": "booking", "steps": []}, [calls(("book_slot", {"slot_id": slot.slot_id})), reply])
    monkeypatch.setattr(agent_router, "get_llm", lambda: llm)
    headers = headers_for(None, {})
    res = client.post("/agent/chat", json={"message": f"Book slot {slot.slot_id}"}, headers=headers)
    events = [json.loads(line[6:]) for line in res.text.splitlines() if line.startswith("data: ")]
    final = events[-1]["data"]
    assert all(e["data"]["ok"] for e in events if e["type"] == "verify")
    assert "https://meet.jklu.example/" in final["text"]
    remember(final["session_id"], headers)

    # Next turn: the agent is told the student's session and link, and may repeat it.
    seen = {}
    llm2 = FakeLLM({"intent": "booking", "steps": []}, [says("Here it is again.")])
    llm2.start = lambda text: seen.setdefault("ctx", text) and FakeLLM.start(llm2, text)
    monkeypatch.setattr(agent_router, "get_llm", lambda: llm2)
    client.post("/agent/chat", json={"message": "What's my meeting link?", "session_id": final["session_id"]},
                headers=headers)
    link = re.search(r"https://meet\.jklu\.example/\S+", final["text"]).group(0).rstrip(".")
    assert "booked session" in seen["ctx"] and link in seen["ctx"]
