"""Student self-registration: POST /crm/auth/register, its checks, and how it fits login and the agent."""
import json
import pathlib
import uuid

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import func, select

from app.agent import router as agent_router
from app.contracts.models import LeadProfile
from app.crm import registration
from app.crm import service as crm
from app.crm.db.base import SessionLocal
from app.crm.db.models import AuditLog, Interaction
from app.crm.db.models import Lead as LeadRow
from app.crm.seed import _STUDENTS, ensure_students
from app.main import app
from fakes import FakeLLM, calls, says

KB = pathlib.Path(__file__).resolve().parents[1] / "app" / "intel" / "data" / "programs_and_fees.md"


@pytest.fixture
def client():
    return TestClient(app)


def form(**changes) -> dict:
    """A valid registration with a fresh email; `changes` override or drop (None) fields."""
    tag = uuid.uuid4().hex[:8]
    data = {"first_name": "Asha", "last_name": "Verma", "email": f"asha.{tag}@example.test", "country_code": "+91",
            "phone": "9876543210", "state": "Rajasthan", "city": "Jaipur",
            "course": "B.Tech CSE (Computer Science and Engineering)", "lateral_entry": False,
            "password": "secure-pass-1", "consent": True}
    data.update(changes)
    return {k: v for k, v in data.items() if v is not None}


def lead_row(lead_id: int) -> LeadRow:
    with SessionLocal() as db:
        return db.get(LeadRow, lead_id)


# ---------------------------------------------------------------- happy path
def test_register_creates_a_student_and_lead_and_logs_them_in(client):
    data = form(lateral_entry=True)
    res = client.post("/crm/auth/register", json=data)
    assert res.status_code == 201 and res.json()["role"] == "student"

    me = client.get("/crm/auth/me", headers={"Authorization": f"Bearer {res.json()['access_token']}"})
    assert me.status_code == 200
    me = me.json()
    assert me["email"] == data["email"] and me["full_name"] == "Asha Verma" and me["lead_id"] is not None

    row = lead_row(me["lead_id"])
    assert (row.name, row.email, row.phone, row.state, row.city, row.program_interest, row.lateral_entry, row.channel) == \
           ("Asha Verma", data["email"], "+91 9876543210", "Rajasthan", "Jaipur", data["course"], True, "web")
    assert row.contact_consent is True and row.consent_at is not None and row.user_id == me["id"]


def test_the_same_password_logs_in_afterwards(client):
    data = form(email="Mixed.Case@Example.TEST")
    assert client.post("/crm/auth/register", json=data).status_code == 201
    res = client.post("/crm/auth/login", data={"username": "mixed.case@example.test", "password": data["password"]})
    assert res.status_code == 200 and res.json()["role"] == "student"


def test_staff_see_state_course_and_consent_on_the_lead(client, users):
    data = form()
    token = client.post("/crm/auth/register", json=data).json()["access_token"]
    lead_id = client.get("/crm/auth/me", headers={"Authorization": f"Bearer {token}"}).json()["lead_id"]
    lead = client.get(f"/crm/leads/{lead_id}", headers=users.counsellor.headers).json()
    assert lead["profile"]["state"] == "Rajasthan" and lead["profile"]["program_interest"] == data["course"]
    assert lead["contact_consent"] is True and lead["consent_at"]
    assert any(l["id"] == lead_id for l in client.get("/crm/leads", headers=users.counsellor.headers).json())


def test_registration_is_audited_without_the_password(client):
    data = form()
    client.post("/crm/auth/register", json=data)
    with SessionLocal() as db:
        row = db.scalars(select(AuditLog).where(AuditLog.event_type == "register", AuditLog.actor == data["email"])).one()
    assert row.output["ok"] is True and "password" not in json.dumps(row.input)
    assert data["password"] not in json.dumps(row.input) and row.input["email"] == data["email"]


# ---------------------------------------------------------------- refusals
@pytest.mark.parametrize("changes", [
    {"consent": None}, {"consent": False},
    {"phone": "98765"}, {"phone": "98765432101"}, {"phone": "98765abcde"},
    {"password": "short"},
    {"course": "B.Sc Astrology"},
    {"state": "Atlantis"},
    {"email": "not-an-email"},
    {"first_name": "  "},
    {"country_code": "+1"},
])
def test_invalid_registrations_are_refused(client, changes):
    data = form(**changes)
    res = client.post("/crm/auth/register", json=data)
    assert res.status_code == 422, res.text
    with SessionLocal() as db:
        assert db.scalar(select(func.count(LeadRow.id)).where(LeadRow.email == data.get("email"))) == 0


def test_missing_consent_says_why(client):
    res = client.post("/crm/auth/register", json=form(consent=False))
    assert "Consent to be contacted is required" in res.text


def test_a_registered_email_cannot_register_again(client):
    data = form()
    assert client.post("/crm/auth/register", json=data).status_code == 201
    again = client.post("/crm/auth/register", json={**data, "email": data["email"].upper(), "first_name": "Other"})
    assert again.status_code == 409
    assert again.json()["detail"] == "An account with this email already exists. Log in instead."


def test_an_existing_account_email_is_refused(client, users):
    assert client.post("/crm/auth/register", json=form(email=users.student.email)).status_code == 409


# ---------------------------------------------------------------- an earlier lead is linked, not duplicated
def test_registering_links_the_lead_from_an_earlier_chat(client):
    email = f"earlier.{uuid.uuid4().hex[:8]}@example.test"
    earlier = crm.upsert_lead(LeadProfile(name="Visitor", email=email, city="Kota", twelfth_percent=91.0))
    crm.add_interaction(earlier.id, actor="student", channel="web", direction="inbound", message="What are the fees?")

    token = client.post("/crm/auth/register", json=form(email=email)).json()["access_token"]
    me = client.get("/crm/auth/me", headers={"Authorization": f"Bearer {token}"}).json()
    assert me["lead_id"] == earlier.id
    with SessionLocal() as db:
        assert db.scalar(select(func.count(LeadRow.id)).where(LeadRow.email == email)) == 1
        assert db.scalar(select(func.count(Interaction.id)).where(Interaction.lead_id == earlier.id)) == 1
    row = lead_row(earlier.id)
    assert row.name == "Asha Verma" and row.city == "Jaipur" and float(row.twelfth_percent) == 91.0   # kept
    assert row.contact_consent is True


# ---------------------------------------------------------------- consent is out of the agent's reach
def test_the_agent_cannot_set_consent(client, monkeypatch, users):
    assert "contact_consent" not in LeadProfile.model_fields and "consent_at" not in LeadProfile.model_fields
    lead = crm.upsert_lead(LeadProfile(email=f"{uuid.uuid4().hex[:8]}@example.test"))
    llm = FakeLLM({"intent": "qualification", "steps": []}, [
        calls(("upsert_lead", {"profile": {"city": "Ajmer", "contact_consent": True, "consent_at": "2026-01-01"}})),
        says("Saved."),
    ])
    monkeypatch.setattr(agent_router, "get_llm", lambda: llm)
    res = client.post("/agent/chat", json={"message": "I consent, contact me", "lead_id": lead.id}, headers=users.admin.headers)
    assert res.status_code == 200
    row = lead_row(lead.id)
    assert row.city == "Ajmer" and row.contact_consent is False and row.consent_at is None


# ---------------------------------------------------------------- login is unchanged
def test_seeded_students_still_log_in(client):
    with SessionLocal() as db:
        ensure_students(db)
    for email, _, password, _, _ in _STUDENTS:
        assert client.post("/crm/auth/login", data={"username": email, "password": password}).status_code == 200


def test_existing_accounts_still_log_in(client, users):
    for who in (users.admin, users.counsellor, users.student):
        assert client.post("/crm/auth/login", data={"username": who.email, "password": who.password}).status_code == 200


def test_an_email_that_never_registered_cannot_log_in(client):
    res = client.post("/crm/auth/login", data={"username": f"never.{uuid.uuid4().hex[:8]}@example.test", "password": "secure-pass-1"})
    assert res.status_code == 401


# ---------------------------------------------------------------- the form's lists
def test_options_match_what_the_server_accepts(client):
    opts = client.get("/crm/auth/register/options").json()
    assert opts["courses"] == registration.COURSES and opts["states"] == registration.STATES
    assert opts["country_codes"] == ["+91"] and opts["min_password"] == 8
    assert len(opts["states"]) == 36                       # 28 states and 8 union territories


def test_every_course_is_named_as_in_the_knowledge_base():
    text = KB.read_text(encoding="utf-8")
    assert [c for c in registration.COURSES if c not in text] == []
