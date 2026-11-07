"""Phase 6: model fallback, rate limits, unhandled errors, demo seed safety and staging."""
import time
import uuid
from types import SimpleNamespace

import pytest
from fastapi.testclient import TestClient

from app.agent import router as agent_router
from app.agent.llm import GeminiLLM
from app.contracts.models import LeadProfile, LeadScore
from app.crm import ratelimit, reports
from app.crm import seed as crm_seed
from app.crm import service as crm
from app.demo_seed import (BULK_LEADS, CLASH_HOLDER, HOT_SILENT_LEAD, OPTED_OUT_LEAD, SCHOLARSHIP_LEAD,
                           assert_safe_to_reset, stage_demo)
from app.main import app
from app.scheduling import seed as sched_seed
from app.scheduling import service as sched
from app.scheduling.models import Counsellor
from fakes import FakeLLM, says

CHIT = {"intent": "chitchat", "needs_clarification": False, "clarifying_question": None, "steps": []}


# ---------------------------------------------------------------- model fallback
class Overloaded(Exception):
    status_code = 503


class BadRequest(Exception):
    status_code = 400


def llm_with(handler, fallback="backup-model", timeout=5.0) -> tuple[GeminiLLM, list[str]]:
    used: list[str] = []

    def create(**kwargs):
        used.append(kwargs["model"])
        return handler(kwargs["model"])

    llm = GeminiLLM(api_key="test", model="main-model", fallback_model=fallback, timeout=timeout)
    llm.client = SimpleNamespace(interactions=SimpleNamespace(create=create))
    return llm, used


def reply(_model):
    return SimpleNamespace(output_text="ok", steps=[])


def test_uses_the_main_model_when_it_works():
    llm, used = llm_with(reply)
    assert llm.write("system", "hi") == "ok" and used == ["main-model"]


def test_falls_back_when_the_main_model_is_overloaded():
    def handler(model):
        if model == "main-model":
            raise Overloaded("high demand")
        return reply(model)

    llm, used = llm_with(handler)
    assert llm.write("system", "hi") == "ok" and used == ["main-model", "backup-model"]


def test_falls_back_when_the_main_model_is_too_slow():
    def handler(model):
        if model == "main-model":
            time.sleep(1)
        return reply(model)

    llm, used = llm_with(handler, timeout=0.1)
    assert llm.write("system", "hi") == "ok" and used == ["main-model", "backup-model"]


def test_goes_straight_to_the_backup_while_the_main_model_is_down():
    def handler(model):
        if model == "main-model":
            raise Overloaded("high demand")
        return reply(model)

    llm, used = llm_with(handler)
    llm.write("system", "first")
    used.clear()
    llm.write("system", "second")
    assert used == ["backup-model"]


def test_a_real_error_does_not_fall_back():
    def handler(_model):
        raise BadRequest("invalid request")

    llm, used = llm_with(handler)
    with pytest.raises(BadRequest):
        llm.write("system", "hi")
    assert used == ["main-model"]


def test_with_both_models_down_the_error_reaches_the_agent_loop():
    def handler(_model):
        raise Overloaded("high demand")

    llm, used = llm_with(handler)
    with pytest.raises(Overloaded):
        llm.write("system", "hi")
    assert used == ["main-model", "backup-model"]


def test_without_a_fallback_there_is_only_one_attempt(monkeypatch):
    monkeypatch.delenv("LLM_FALLBACK_MODEL", raising=False)

    def handler(_model):
        raise Overloaded("high demand")

    llm, used = llm_with(handler, fallback=None)
    with pytest.raises(Overloaded):
        llm.write("system", "hi")
    assert used == ["main-model"]


# ---------------------------------------------------------------- rate limits
@pytest.fixture
def limits_on(monkeypatch):
    monkeypatch.setenv("RATE_LIMITS_ENABLED", "1")
    ratelimit.login_failures.reset()
    ratelimit.chat_requests.reset()
    yield
    ratelimit.login_failures.reset()
    ratelimit.chat_requests.reset()


@pytest.fixture
def client():
    return TestClient(app)


def test_repeated_wrong_passwords_are_blocked_even_with_the_right_one(client, users, limits_on):
    s = users.student
    for _ in range(ratelimit.login_failures.limit):
        assert client.post("/crm/auth/login", data={"username": s.email, "password": "wrong"}).status_code == 401
    res = client.post("/crm/auth/login", data={"username": s.email, "password": s.password})
    assert res.status_code == 429 and "Retry-After" in res.headers


def test_a_login_block_does_not_affect_other_accounts(client, users, limits_on):
    for _ in range(ratelimit.login_failures.limit):
        client.post("/crm/auth/login", data={"username": users.student.email, "password": "wrong"})
    other = users.other_student
    assert client.post("/crm/auth/login", data={"username": other.email, "password": other.password}).status_code == 200


def test_a_successful_login_clears_earlier_failures(client, users, limits_on):
    s = users.student
    for _ in range(ratelimit.login_failures.limit - 1):
        client.post("/crm/auth/login", data={"username": s.email, "password": "wrong"})
    assert client.post("/crm/auth/login", data={"username": s.email, "password": s.password}).status_code == 200
    assert client.post("/crm/auth/login", data={"username": s.email, "password": "wrong"}).status_code == 401
    assert not ratelimit.login_failures.blocked(f"testclient|{s.email}")


def test_chat_is_limited_before_any_model_call(client, monkeypatch, limits_on):
    def no_model():
        raise AssertionError("the model must not be reached")

    monkeypatch.setattr(agent_router, "get_llm", no_model)
    for _ in range(ratelimit.chat_requests.limit):
        ratelimit.chat_requests.hit("testclient")
    assert client.post("/agent/chat", json={"message": "hello"}).status_code == 429


def test_chat_below_the_limit_still_works(client, monkeypatch, limits_on):
    monkeypatch.setattr(agent_router, "get_llm", lambda: FakeLLM(CHIT, [says("Hello.")]))
    assert client.post("/agent/chat", json={"message": "hello"}).status_code == 200


def test_a_refusal_is_audited(client, users, limits_on):
    for _ in range(ratelimit.chat_requests.limit):
        ratelimit.chat_requests.hit("testclient")
    client.post("/agent/chat", json={"message": "hello"})
    rows = client.get("/crm/audit", params={"type": "rate_limited"}, headers=users.admin.headers).json()
    assert rows and rows[0]["tool_name"] == "/agent/chat"


# ---------------------------------------------------------------- unhandled errors
def test_a_crash_returns_json_with_cors_headers(monkeypatch, users):
    def crash():
        raise RuntimeError("secret detail")

    monkeypatch.setattr(reports, "funnel", crash)
    res = TestClient(app, raise_server_exceptions=False).get(
        "/crm/analytics/funnel", headers={**users.counsellor.headers, "Origin": "http://localhost:5173"})
    assert res.status_code == 500
    assert "secret detail" not in res.text and res.json()["detail"]
    assert res.headers["access-control-allow-origin"] == "http://localhost:5173"


# ---------------------------------------------------------------- demo seed
@pytest.mark.parametrize("url", [
    "postgresql+psycopg://u:p@db.example.com:5432/admissions",
    "postgresql+psycopg://u:p@localhost:5432/production",
    "postgresql+psycopg://u:p@localhost:5432/admissions_test",
])
def test_reset_refuses_anything_but_the_local_demo_database(url):
    with pytest.raises(SystemExit):
        assert_safe_to_reset(url)


def test_reset_accepts_the_local_demo_database():
    assert_safe_to_reset("postgresql+psycopg://buildathon:buildathon@localhost:5432/admissions")


def test_seed_data_uses_only_reserved_addresses_and_numbers():
    for lead in crm_seed._LEADS:
        assert lead[1].endswith("@example.test"), lead[1]
        assert lead[2].startswith("90000000"), lead[2]


def test_seed_messages_state_no_institutional_facts():
    """Seeded lines show as the agent's words, so they must not promise or state anything about JKLU."""
    text = " ".join(crm_seed._OUTBOUND_MSG).lower()
    for claim in ("qualify", "scholarship", "emi", "batch", "seats", "brochure", "jklu.edu"):
        assert claim not in text, claim


def seed_lead(name: str, tier: str = "warm") -> int:
    tag = uuid.uuid4().hex[:8]
    lead_id = crm.upsert_lead(LeadProfile(name=name, email=f"{tag}@example.test", program_interest="B.Tech CSE")).id
    score = LeadScore(score=60, tier=tier, reasons=["test"])
    crm.update_lead_score(lead_id, score.score, score.tier, score.reasons)
    return lead_id


def test_stage_demo_sets_up_every_demo_moment(users):
    sched_seed.ensure_counsellors()
    with sched.SessionLocal() as db:
        if not db.query(Counsellor).filter_by(name="Ms. Rekha Verma").first():
            db.add(Counsellor(name="Ms. Rekha Verma"))
            db.commit()

    names = [CLASH_HOLDER, HOT_SILENT_LEAD, SCHOLARSHIP_LEAD, OPTED_OUT_LEAD, *BULK_LEADS]
    ids = {name: seed_lead(name) for name in names}

    staged = stage_demo()

    slot = staged["clash_slot"]
    holder_bookings = sched.list_bookings(ids[CLASH_HOLDER])
    assert [b["slot_id"] for b in holder_bookings] == [slot.slot_id]
    clash = sched.book_slot(ids[HOT_SILENT_LEAD], slot.slot_id)
    assert not clash.ok and clash.reason == "slot_taken" and clash.alternatives

    assert crm.get_lead(ids[OPTED_OUT_LEAD]).opted_out
    templates = {name: [f["template"] for f in sched.list_followups(ids[name], "pending")]
                 for name in (HOT_SILENT_LEAD, SCHOLARSHIP_LEAD, OPTED_OUT_LEAD)}
    assert templates == {HOT_SILENT_LEAD: ["hot_reminder"], SCHOLARSHIP_LEAD: ["scholarship"], OPTED_OUT_LEAD: ["warm_nudge"]}
