"""Agent loop + /agent/chat SSE endpoint with the LLM mocked (SPEC scenarios S1, S2).

Tools are real (intel KB + CRM on the test database); only Gemini is faked.
"""
import json
import uuid
from datetime import timedelta

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select

from app.agent import loop as agent_loop
from app.agent import router as agent_router
from app.agent import tools_schema
from app.agent.loop import ESCALATED_MSG, FALLBACK_MSG, MAX_TOOL_STEPS, SENSITIVE_NOTE
from app.contracts.models import LeadProfile
from app.crm import service as crm_service
from app.crm.db.base import SessionLocal
from app.crm.db.models import Approval, AuditLog, Interaction
from app.main import app
from app.scheduling import clock
from app.scheduling import service as sched_service
from app.scheduling.models import SlotRow
from app.scheduling.seed import seed_slots
from fakes import FakeLLM, calls, says

FEES = "programs_and_fees.md#bachelor-of-technology-b-tech"
ELIG = "admissions_and_eligibility.md#b-tech-eligibility-criteria"
HOSTEL = "scholarships.md#special-circumstances-and-out-of-scope-clarifications"


@pytest.fixture(autouse=True)
def no_backoff(monkeypatch):
    monkeypatch.setattr(agent_loop, "BACKOFF_SECONDS", (0, 0))


@pytest.fixture
def client():
    return TestClient(app)


def chat(client, monkeypatch, llm, message, headers=None, **body):
    monkeypatch.setattr(agent_router, "get_llm", lambda: llm)
    res = client.post("/agent/chat", json={"message": message, **body}, headers=headers)
    assert res.status_code == 200, res.text
    assert res.headers["content-type"].startswith("text/event-stream")
    events = [json.loads(line[6:]) for line in res.text.splitlines() if line.startswith("data: ")]
    assert events[-1]["type"] == "final"
    return events


def types(events):
    return [e["type"] for e in events]


def streamed_text(events):
    return "".join(e["data"]["delta"] for e in events if e["type"] == "message")


def by_type(events, t):
    return [e for e in events if e["type"] == t]


def rows(model, **where):
    with SessionLocal() as db:
        stmt = select(model)
        for k, v in where.items():
            stmt = stmt.where(getattr(model, k) == v)
        return db.scalars(stmt).all()


# ---------------------------------------------------------------- S1
def test_s1_fee_and_eligibility_answered_with_citations(client, monkeypatch):
    llm = FakeLLM(
        plan={"intent": "institutional_question",
              "steps": [{"goal": "look up fee", "tool": "search_knowledge"},
                        {"goal": "look up eligibility", "tool": "search_knowledge"}]},
        script=[
            calls(("search_knowledge", {"query": "B.Tech CSE fee"}),
                  ("search_knowledge", {"query": "B.Tech eligibility criteria"})),
            says(f"The B.Tech CSE annual academic fee is INR 2,65,000 per year [{FEES}]. "
                 f"You need a minimum of 60% aggregate in Class 10th and 12th with Physics and Mathematics, "
                 f"and JEE Mains 2026, CUET 2026 or JKLU-EET [{ELIG}]."),
        ],
    )
    events = chat(client, monkeypatch, llm, "What is the B.Tech CSE fee and eligibility?")

    t = types(events)
    assert t[0] == "plan" and events[0]["data"]["intent"] == "institutional_question"
    assert t.count("tool_call") == 2 and t.count("tool_result") == 2
    assert t.index("verify") > t.index("tool_result") and t.index("message") > t.index("verify")
    assert all(v["data"]["ok"] for v in by_type(events, "verify"))

    final = events[-1]["data"]
    retrieved = {c["source"] for r in by_type(events, "tool_result") for c in r["data"]["result"]["chunks"]}
    assert set(final["citations"]) == {FEES, ELIG} and set(final["citations"]) <= retrieved
    assert "2,65,000" in streamed_text(events) and streamed_text(events) == final["text"]
    assert final["escalated"] is False

    session, lead = final["session_id"], final["lead_id"]
    audit = rows(AuditLog, session_id=session)
    assert len(audit) == len([e for e in events if e["type"] != "message"])
    assert {a.event_type for a in audit} >= {"plan", "tool_call", "tool_result", "verify", "final"}
    assert all(a.lead_id == lead and a.actor == "agent" for a in audit)
    convo = rows(Interaction, lead_id=lead)
    assert [i.direction for i in convo] == ["inbound", "outbound"] and convo[1].message == final["text"]
    assert rows(Approval, lead_id=lead) == []


def test_s1_second_turn_keeps_session_and_history(client, monkeypatch):
    first = chat(client, monkeypatch, FakeLLM({"intent": "chitchat", "steps": []}, [says("Hi! How can I help?")]),
                 "Hello")[-1]["data"]
    llm = FakeLLM({"intent": "chitchat", "steps": []}, [says("Happy to help.")])
    seen = {}
    llm.start = lambda text: seen.setdefault("ctx", text) and FakeLLM.start(llm, text)
    second = chat(client, monkeypatch, llm, "Thanks", session_id=first["session_id"])[-1]["data"]
    assert second["lead_id"] == first["lead_id"] and second["session_id"] == first["session_id"]
    assert "Student: Hello" in seen["ctx"] and "Assistant: Hi! How can I help?" in seen["ctx"]


# ---------------------------------------------------------------- S2
def test_s2_hostel_waiver_cited_no_and_escalated(client, monkeypatch):
    """The KB does answer this one ('no'), so the agent cites it and escalates the exception request."""
    llm = FakeLLM(
        plan={"intent": "sensitive_request", "steps": [{"goal": "check waiver policy", "tool": "search_knowledge"}]},
        script=[
            calls(("search_knowledge", {"query": "hostel fee waiver"})),
            says(f"JKLU does not offer hostel fee waivers under standard merit scholarships; "
                 f"scholarships apply to academic fees only [{HOSTEL}]."),
        ],
    )
    events = chat(client, monkeypatch, llm, "Is there a hostel fee waiver?")
    final = events[-1]["data"]

    assert final["citations"] == [HOSTEL] and final["text"].endswith(SENSITIVE_NOTE)
    assert final["escalated"] is True
    esc = by_type(events, "escalation")[0]["data"]
    assert esc["recorded"] and esc["approval_id"] == final["approval_id"]
    approval = rows(Approval, id=final["approval_id"])[0]
    assert approval.action == "escalate_question" and approval.status == "pending"
    assert approval.lead_id == final["lead_id"] and approval.payload["question"] == "Is there a hostel fee waiver?"


def test_s2_question_not_in_kb_is_escalated_without_guessing(client, monkeypatch):
    llm = FakeLLM(
        plan={"intent": "institutional_question", "steps": [{"goal": "search", "tool": "search_knowledge"}]},
        script=[calls(("search_knowledge", {"query": "fee waiver for children of army personnel"})),
                says("[NOT_IN_KB] The retrieved documents do not cover this.")],
    )
    events = chat(client, monkeypatch, llm, "Do you offer a fee waiver for children of army personnel?")
    final = events[-1]["data"]

    assert streamed_text(events) == final["text"] == ESCALATED_MSG
    assert final["escalated"] is True and final["citations"] == []
    verify = by_type(events, "verify")[0]["data"]
    assert verify["ok"] is False and verify["action"] == "escalate"
    assert rows(Approval, id=final["approval_id"])[0].action == "escalate_question"


def test_fabricated_fee_never_reaches_the_student(client, monkeypatch):
    fake = says(f"Yes! Army families get a 50% waiver, so you pay INR 1,45,000 [programs_and_fees.md#bachelor-of-design-b-des].")
    llm = FakeLLM(
        plan={"intent": "institutional_question", "steps": []},
        script=[calls(("search_knowledge", {"query": "fee waiver for children of army personnel"})), fake, fake],
    )
    events = chat(client, monkeypatch, llm, "Do you offer a fee waiver for children of army personnel?")

    failed = [v["data"] for v in by_type(events, "verify") if not v["data"]["ok"] and v["data"]["check"] == "grounding"]
    assert len(failed) == 2 and failed[0]["action"] == "replan"
    assert "145000" in failed[0]["ungrounded_numbers"]
    assert len(llm.feedback) == 1                      # one replan, then escalation
    assert streamed_text(events) == ESCALATED_MSG
    assert "1,45,000" not in json.dumps([e for e in events if e["type"] in ("message", "final")])


# ---------------------------------------------------------------- recovery
def test_tool_error_is_retried_then_succeeds(client, monkeypatch):
    real = tools_schema.execute
    failures = {"left": 2}

    def flaky(name, args, lead_id):
        if failures["left"]:
            failures["left"] -= 1
            raise TimeoutError("kb timeout")
        return real(name, args, lead_id)

    monkeypatch.setattr(tools_schema, "execute", flaky)
    llm = FakeLLM({"intent": "institutional_question", "steps": []},
                  [calls(("search_knowledge", {"query": "B.Tech CSE fee"})),
                   says(f"The B.Tech annual academic fee is INR 2,65,000 [{FEES}].")])
    events = chat(client, monkeypatch, llm, "B.Tech fee?")

    assert [r["data"]["attempt"] for r in by_type(events, "retry")] == [1, 2]
    assert by_type(events, "tool_result")[0]["data"]["ok"] is True
    assert "2,65,000" in events[-1]["data"]["text"]


def test_llm_down_gives_graceful_fallback(client, monkeypatch):
    llm = FakeLLM(ConnectionError("gemini unreachable"), [ConnectionError("gemini unreachable")])
    events = chat(client, monkeypatch, llm, "B.Tech fee?")
    assert len(by_type(events, "retry")) == 4          # 2 for plan, 2 for act
    assert events[-1]["data"]["text"] == FALLBACK_MSG


def test_hanging_llm_is_cut_off_and_the_turn_still_ends(client, monkeypatch):
    """A model call that never returns (e.g. an SDK sleeping on Retry-After) must not hang the chat."""
    import time as _time

    class HangingLLM(FakeLLM):
        def plan(self, system, prompt):
            _time.sleep(5)
            return {"intent": "chitchat", "steps": []}

    monkeypatch.setattr(agent_loop, "LLM_TIMEOUT_SECONDS", 0.2)
    llm = HangingLLM({}, [says("never reached")])
    llm.act = lambda *a: _time.sleep(5)
    started = _time.monotonic()
    events = chat(client, monkeypatch, llm, "hello?")
    assert _time.monotonic() - started < 4
    assert len(by_type(events, "retry")) == 4 and events[-1]["data"]["text"] == FALLBACK_MSG


def test_turn_budget_stops_further_retries(client, monkeypatch):
    monkeypatch.setattr(agent_loop, "TURN_BUDGET_SECONDS", 0)
    llm = FakeLLM(ConnectionError("down"), [ConnectionError("down")])
    events = chat(client, monkeypatch, llm, "hello?")
    assert by_type(events, "retry") == [] and events[-1]["data"]["text"] == FALLBACK_MSG


def test_step_limit_stops_runaway_tool_calls(client, monkeypatch):
    llm = FakeLLM({"intent": "unknown", "steps": []}, [calls(("search_knowledge", {"query": "fees"}))])
    events = chat(client, monkeypatch, llm, "loop forever")
    assert types(events).count("tool_call") == MAX_TOOL_STEPS
    assert by_type(events, "error")[-1]["data"]["error"] == "step_limit"
    assert events[-1]["data"]["text"] == FALLBACK_MSG


def test_missing_llm_config_streams_an_error(client, monkeypatch):
    def broken():
        raise RuntimeError("Set LLM_API_KEY and LLM_MODEL in .env")

    monkeypatch.setattr(agent_router, "get_llm", broken)
    res = client.post("/agent/chat", json={"message": "hi"})
    assert res.status_code == 200 and '"type": "error"' in res.text and '"type": "final"' in res.text


def test_unknown_lead_is_404(client, users):
    res = client.post("/agent/chat", json={"message": "hi", "lead_id": 999999}, headers=users.counsellor.headers)
    assert res.status_code == 404


# ---------------------------------------------------------------- sessions
def test_session_id_alone_continues_the_same_lead(client, monkeypatch):
    first = chat(client, monkeypatch, FakeLLM({"intent": "chitchat", "steps": []}, [says("Hi!")]), "Hello")[-1]["data"]
    again = chat(client, monkeypatch, FakeLLM({"intent": "chitchat", "steps": []}, [says("Sure.")]), "More",
                 session_id=first["session_id"])[-1]["data"]
    assert again["lead_id"] == first["lead_id"]


def test_session_of_another_lead_is_rejected(client, monkeypatch, users):
    first = chat(client, monkeypatch, FakeLLM({"intent": "chitchat", "steps": []}, [says("Hi!")]), "Hello")[-1]["data"]
    other = crm_service.upsert_lead(LeadProfile(email=f"{uuid.uuid4().hex[:8]}@example.test")).id
    res = client.post("/agent/chat", json={"message": "hi", "session_id": first["session_id"], "lead_id": other},
                      headers=users.counsellor.headers)
    assert res.status_code == 409


# ---------------------------------------------------------------- S4 via the agent
def test_booking_clash_offers_real_alternatives_and_never_claims_booking(client, monkeypatch):
    seed_slots()
    now = clock.now().astimezone(clock.IST)
    slot = sched_service.get_slots(now.date().isoformat(), (now + timedelta(days=7)).date().isoformat())[0]
    rival = crm_service.upsert_lead(LeadProfile(email=f"{uuid.uuid4().hex[:8]}@example.test")).id
    assert sched_service.book_slot(rival, slot.slot_id).ok

    def offer_alternatives(convo):
        booking = next(r for name, r, _ in llm.tool_results if name == "book_slot")
        times = ", ".join(f"{a['start']} with {a['counsellor']}" for a in booking["alternatives"])
        return says(f"Sorry, that slot was just taken. Free slots nearby: {times}. Which one suits you?")

    llm = FakeLLM({"intent": "booking", "steps": [{"goal": "book", "tool": "book_slot"}]},
                  [calls(("book_slot", {"slot_id": slot.slot_id})),
                   says("Great news, you're booked!"),          # wrong: verifier must reject this
                   offer_alternatives])
    events = chat(client, monkeypatch, llm, f"Book slot {slot.slot_id} for me")

    result = by_type(events, "tool_result")[0]["data"]["result"]
    assert result["ok"] is False and result["reason"] == "slot_taken" and len(result["alternatives"]) == 3
    booking_checks = [v["data"] for v in by_type(events, "verify") if v["data"]["check"] == "booking"]
    assert booking_checks[0]["ok"] is False and booking_checks[0]["action"] == "replan"
    assert booking_checks[-1]["ok"] is True
    final = events[-1]["data"]["text"]
    assert "booked" not in final and all(a["start"] in final for a in result["alternatives"])
    with SessionLocal() as db:
        assert db.scalars(select(SlotRow).where(SlotRow.lead_id == events[-1]["data"]["lead_id"])).all() == []
