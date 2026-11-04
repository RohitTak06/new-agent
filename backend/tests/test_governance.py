"""Auth, RBAC, approvals and audit (SPEC S7 at service level, S8, S9)."""
import json
import re
import uuid
from concurrent.futures import ThreadPoolExecutor
from datetime import timedelta

import jwt
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select, text, update
from sqlalchemy.exc import DBAPIError

from app.agent import router as agent_router
from app.contracts import tools
from app.contracts.models import LeadProfile
from app.crm import approvals
from app.crm import service as crm
from app.crm.auth import CurrentUser, create_token
from app.crm.db.base import SessionLocal
from app.crm.db.models import Approval, AuditLog, Interaction, User
from app.main import app
from app.scheduling import clock, followups
from app.scheduling import service as sched
from app.scheduling.models import SlotRow
from app.scheduling.seed import seed_slots
from fakes import FakeLLM, says

PUBLIC_ROUTES = {
    ("get", "/health"), ("get", "/agent/health"), ("get", "/crm/health"), ("get", "/intel/health"),
    ("get", "/scheduling/health"), ("post", "/crm/auth/login"), ("post", "/agent/chat"),
}


@pytest.fixture
def client():
    return TestClient(app)


@pytest.fixture(scope="module", autouse=True)
def slots():
    seed_slots()


def new_lead(**profile) -> int:
    tag = uuid.uuid4().hex[:8]
    return crm.upsert_lead(LeadProfile(**{"name": f"Test {tag}", "email": f"{tag}@example.test", **profile})).id


def staff_user(users) -> CurrentUser:
    c = users.counsellor
    return CurrentUser(id=c.id, email=c.email, full_name="Counsellor", role=c.role)


def audit_rows(**where):
    with SessionLocal() as db:
        stmt = select(AuditLog)
        for k, v in where.items():
            stmt = stmt.where(getattr(AuditLog, k) == v)
        return db.scalars(stmt).all()


# ---------------------------------------------------------------- every route is guarded
def all_operations():
    for path, ops in app.openapi()["paths"].items():
        for method in ops:
            yield method, path


def test_public_routes_exist():
    """Anything not listed in PUBLIC_ROUTES must return 401 (next test), so opening a route is deliberate."""
    assert PUBLIC_ROUTES <= set(all_operations())


@pytest.mark.parametrize("method,path", sorted(set(all_operations()) - PUBLIC_ROUTES))
def test_every_other_route_needs_a_token(client, method, path):
    url = re.sub(r"\{[^}]+\}", "1", path)
    assert client.request(method, url).status_code == 401, f"{method} {path} is open"


# ---------------------------------------------------------------- login and tokens
def test_login_and_me(client, users):
    s = users.student
    res = client.post("/crm/auth/login", data={"username": s.email, "password": s.password})
    assert res.status_code == 200 and res.json()["role"] == "student"
    me = client.get("/crm/auth/me", headers={"Authorization": f"Bearer {res.json()['access_token']}"}).json()
    assert me["email"] == s.email and me["lead_id"] == s.lead_id


def test_bad_logins_are_refused_and_audited_without_the_password(client, users):
    a = users.admin
    assert client.post("/crm/auth/login", data={"username": a.email, "password": "wrong-pass-123"}).status_code == 401
    assert client.post("/crm/auth/login", data={"username": "nobody@example.test", "password": "x"}).status_code == 401
    rows = audit_rows(event_type="login", actor=a.email)
    assert any(r.output == {"ok": False} for r in rows)
    assert "wrong-pass-123" not in json.dumps([[r.input, r.output] for r in rows])


def test_expired_tampered_and_wrong_key_tokens_are_refused(client, users):
    s = users.student
    expired = create_token(s.id, s.role, hours=-1)
    forged = jwt.encode({"sub": str(users.admin.id), "role": "admin", "exp": 9999999999}, "change-me", algorithm="HS256")
    for token in (expired, forged, "not-a-token", expired[:-3] + "abc"):
        assert client.get("/crm/auth/me", headers={"Authorization": f"Bearer {token}"}).status_code == 401
    # A bad token is a 401 on the open chat route too, never silently "anonymous"
    assert client.post("/agent/chat", json={"message": "hi"}, headers={"Authorization": "Bearer nope"}).status_code == 401


def test_deactivated_user_is_locked_out_at_once(client):
    with SessionLocal() as db:
        user = User(email=f"{uuid.uuid4().hex[:8]}@example.test", full_name="Gone", role="counsellor",
                    password_hash=crm.hash_password("pw-gone-123"), is_active=True)
        db.add(user)
        db.commit()
        uid, email = user.id, user.email
    headers = {"Authorization": f"Bearer {create_token(uid, 'counsellor')}"}
    assert client.get("/crm/leads", headers=headers).status_code == 200
    with SessionLocal() as db:
        db.execute(update(User).where(User.id == uid).values(is_active=False))
        db.commit()
    assert client.get("/crm/leads", headers=headers).status_code == 401
    assert client.post("/crm/auth/login", data={"username": email, "password": "pw-gone-123"}).status_code == 401


@pytest.mark.parametrize("secret", ["", "change-me", "short"])
def test_placeholder_jwt_secret_is_refused(monkeypatch, secret):
    monkeypatch.setenv("JWT_SECRET", secret)
    with pytest.raises(RuntimeError):
        create_token(1, "admin")


# ---------------------------------------------------------------- S8 RBAC
def test_s8_student_is_limited_to_their_own_data(client, users):
    s, other = users.student, users.other_student
    h = s.headers
    for method, url in [("get", "/crm/leads"), ("get", f"/crm/leads/{other.lead_id}"),
                        ("get", f"/crm/leads/{other.lead_id}/interactions"), ("get", "/crm/approvals"),
                        ("get", "/crm/audit"), ("get", "/crm/analytics/funnel"), ("get", "/intel/knowledge"),
                        ("post", "/intel/knowledge/reload"), ("get", f"/scheduling/messages/{other.lead_id}"),
                        ("get", "/scheduling/followups"), ("patch", f"/crm/leads/{other.lead_id}/opt-out")]:
        assert client.request(method, url, headers=h).status_code == 403, url
    assert client.post("/scheduling/clock/advance", json={"hours": 1}, headers=h).status_code == 403
    assert client.post("/scheduling/book", json={"lead_id": other.lead_id, "slot_id": "1"}, headers=h).status_code == 403
    for url in (f"/crm/leads/{s.lead_id}", f"/crm/leads/{s.lead_id}/interactions", f"/scheduling/messages/{s.lead_id}"):
        assert client.get(url, headers=h).status_code == 200, url
    assert any(r.tool_name == "/crm/audit" for r in audit_rows(event_type="access_denied", actor=s.email))


def test_s8_nonexistent_lead_looks_the_same_to_a_student(client, users):
    assert client.get("/crm/leads/999999", headers=users.student.headers).status_code == 403


def test_s8_counsellor_can_read_but_not_manage_the_kb(client, users):
    h = users.counsellor.headers
    for url in ("/crm/leads", f"/crm/leads/{users.student.lead_id}", "/crm/approvals", "/crm/audit",
                "/crm/analytics/funnel", "/intel/knowledge"):
        assert client.get(url, headers=h).status_code == 200, url
    assert client.post("/intel/knowledge/reload", headers=h).status_code == 403


def test_s8_admin_can_manage_the_kb(client, users):
    res = client.post("/intel/knowledge/reload", headers=users.admin.headers)
    assert res.status_code == 200 and res.json()["total_chunks"] > 0
    assert audit_rows(event_type="api_action", tool_name="reload_knowledge", actor=users.admin.email)


# ---------------------------------------------------------------- chat access
def _chat(client, monkeypatch, message="Hello", headers=None, **body):
    monkeypatch.setattr(agent_router, "get_llm", lambda: FakeLLM({"intent": "chitchat", "steps": []}, [says("Hi!")]))
    return client.post("/agent/chat", json={"message": message, **body}, headers=headers)


def _final(res) -> dict:
    return [json.loads(l[6:]) for l in res.text.splitlines() if l.startswith("data: ")][-1]["data"]


def test_anonymous_chat_works_but_cannot_name_a_lead(client, monkeypatch, users):
    assert _chat(client, monkeypatch).status_code == 200
    assert _chat(client, monkeypatch, lead_id=users.student.lead_id).status_code == 401


def test_student_chat_always_uses_their_own_lead(client, monkeypatch, users):
    s = users.student
    assert _final(_chat(client, monkeypatch, headers=s.headers))["lead_id"] == s.lead_id
    assert _chat(client, monkeypatch, headers=s.headers, lead_id=users.other_student.lead_id).status_code == 403


def test_account_sessions_cannot_be_taken_over(client, monkeypatch, users):
    sid = _final(_chat(client, monkeypatch, headers=users.student.headers))["session_id"]
    assert _chat(client, monkeypatch, session_id=sid).status_code == 401
    assert _chat(client, monkeypatch, headers=users.other_student.headers, session_id=sid).status_code == 403
    assert _chat(client, monkeypatch, headers=users.student.headers, session_id=sid).status_code == 200


def test_student_without_a_lead_gets_one_linked_on_first_chat(client, monkeypatch):
    with SessionLocal() as db:
        user = User(email=f"{uuid.uuid4().hex[:8]}@example.test", full_name="New Student", role="student",
                    password_hash="x", is_active=True)
        db.add(user)
        db.commit()
        uid = user.id
    headers = {"Authorization": f"Bearer {create_token(uid, 'student')}"}
    lead = _final(_chat(client, monkeypatch, headers=headers))["lead_id"]
    assert crm.lead_owner(lead) == uid
    assert _final(_chat(client, monkeypatch, headers=headers))["lead_id"] == lead


def test_session_view_hides_the_trace_from_students(client, monkeypatch, users):
    sid = _final(_chat(client, monkeypatch, "Hello there", headers=users.student.headers))["session_id"]
    mine = client.get(f"/agent/sessions/{sid}", headers=users.student.headers)
    assert mine.status_code == 200 and "trace" not in mine.json()
    assert [m["message"] for m in mine.json()["messages"]] == ["Hello there", "Hi!"]
    assert client.get(f"/agent/sessions/{sid}", headers=users.other_student.headers).status_code == 403
    staff = client.get(f"/agent/sessions/{sid}", headers=users.counsellor.headers).json()
    assert {t["event_type"] for t in staff["trace"]} >= {"plan", "final"}


# ---------------------------------------------------------------- S7 approval gate
def test_s7_fee_waiver_runs_only_after_approval(client, users):
    lead = new_lead()
    req = tools.request_approval("fee_waiver", {"lead_id": lead, "reason": "family hardship"})
    assert req.status == "pending"
    assert sched.list_messages(lead) == [] and crm.list_interactions(lead) == []    # nothing executed
    assert req.approval_id in [a["id"] for a in client.get("/crm/approvals?status=pending",
                                                           headers=users.counsellor.headers).json()]

    url = f"/crm/approvals/{req.approval_id}/approve"
    assert client.post(url, json={}, headers=users.student.headers).status_code == 403
    assert sched.list_messages(lead) == []

    res = client.post(url, json={"note": "Verified documents"}, headers=users.counsellor.headers)
    assert res.status_code == 200
    body = res.json()
    assert body["status"] == "approved" and body["outcome"]["notified"] is True
    assert body["resolved_by"] == users.counsellor.id
    assert len(sched.list_messages(lead)) == 1                                      # student notified
    assert "Verified documents" in crm.list_interactions(lead)[0]["message"]        # lead annotated

    assert client.post(url, json={}, headers=users.counsellor.headers).status_code == 409
    assert len(sched.list_messages(lead)) == 1                                      # not run twice

    trail = audit_rows(approval_id=req.approval_id)
    assert {r.event_type for r in trail} == {"approval_requested", "approval_decision"}
    decision = next(r for r in trail if r.event_type == "approval_decision")
    assert decision.actor == users.counsellor.email and decision.lead_id == lead


def test_two_counsellors_approving_together_run_it_once(users):
    lead = new_lead()
    req = tools.request_approval("fee_waiver", {"lead_id": lead})
    user = staff_user(users)

    def attempt(_):
        try:
            return approvals.approve(req.approval_id, user)["status"]
        except approvals.ApprovalError as exc:
            return exc.status_code

    with ThreadPoolExecutor(max_workers=4) as pool:
        results = list(pool.map(attempt, range(4)))
    assert sorted(map(str, results)) == ["409", "409", "409", "approved"]
    assert len(sched.list_messages(lead)) == 1


def test_escalated_question_needs_the_counsellors_own_reply(client, users):
    lead = new_lead()
    req = tools.request_approval("escalate_question", {"lead_id": lead, "question": "Army family waiver?"})
    url = f"/crm/approvals/{req.approval_id}/approve"
    assert client.post(url, json={}, headers=users.counsellor.headers).status_code == 422
    with SessionLocal() as db:
        assert db.get(Approval, req.approval_id).status == "pending"

    reply = "Please contact the admissions office; I will call you tomorrow."
    assert client.post(url, json={"reply": reply}, headers=users.counsellor.headers).status_code == 200
    assert [m["text"] for m in sched.list_messages(lead)] == [reply]


def test_reject_runs_nothing_and_tells_the_student(client, users):
    lead = new_lead()
    req = tools.request_approval("fee_waiver", {"lead_id": lead})
    url = f"/crm/approvals/{req.approval_id}/reject"
    assert client.post(url, json={}, headers=users.counsellor.headers).status_code == 422       # reason required
    res = client.post(url, json={"reason": "Documents incomplete."}, headers=users.counsellor.headers)
    assert res.json()["status"] == "rejected" and res.json()["reason"] == "Documents incomplete."
    [msg] = sched.list_messages(lead)
    assert "Documents incomplete." in msg["text"] and "call" in msg["text"]
    assert not any((i["meta"] or {}).get("fee_waiver") for i in crm.list_interactions(lead))


def _free_slot(offset=0):
    now = clock.now().astimezone(clock.IST)
    return sched.get_slots(now.date().isoformat(), (now + timedelta(days=7)).date().isoformat())[offset]


def test_booking_override_moves_the_slot_and_tells_both_students(client, users):
    holder, wanted_by = new_lead(), new_lead()
    slot, own = _free_slot(0), _free_slot(1)
    assert sched.book_slot(holder, slot.slot_id).ok and sched.book_slot(wanted_by, own.slot_id).ok
    req = tools.request_approval("booking_override", {"lead_id": wanted_by, "slot_id": slot.slot_id})
    res = client.post(f"/crm/approvals/{req.approval_id}/approve", json={}, headers=users.counsellor.headers)
    assert res.status_code == 200, res.text
    outcome = res.json()["outcome"]
    assert outcome["displaced_lead_id"] == holder and outcome["released_slot_ids"] == [own.slot_id]
    with SessionLocal() as db:
        assert db.get(SlotRow, int(slot.slot_id)).lead_id == wanted_by
        released = db.get(SlotRow, int(own.slot_id))
        assert released.status == "free" and released.lead_id is None
    assert "confirmed" in sched.list_messages(wanted_by)[0]["text"]
    assert "Free slots nearby" in sched.list_messages(holder)[0]["text"]


def test_bulk_message_reports_opted_out_leads(client, users):
    ok_lead, out_lead = new_lead(), new_lead()
    crm.opt_out_lead(out_lead)
    req = tools.request_approval("bulk_message", {"lead_ids": [ok_lead, out_lead], "channel": "email",
                                                  "text": "Open day update"})
    assert sched.list_messages(ok_lead) == []
    outcome = client.post(f"/crm/approvals/{req.approval_id}/approve", json={},
                          headers=users.counsellor.headers).json()["outcome"]
    assert outcome["sent"] == [ok_lead] and outcome["refused"] == [{"lead_id": out_lead, "error": "opted_out"}]
    assert sched.list_messages(out_lead) == []


@pytest.mark.parametrize("action,payload", [("delete_everything", {}),
                                            ("booking_override", {"slot_id": "999999"})])
def test_unknown_or_failing_action_stays_pending(client, users, action, payload):
    lead = new_lead()
    req = tools.request_approval(action, {"lead_id": lead, **payload})
    res = client.post(f"/crm/approvals/{req.approval_id}/approve", json={}, headers=users.counsellor.headers)
    assert res.status_code == 422
    with SessionLocal() as db:
        row = db.get(Approval, req.approval_id)
        assert row.status == "pending" and row.resolved_by is None


def test_failed_execution_is_audited(client, users):
    req = tools.request_approval("booking_override", {"lead_id": new_lead(), "slot_id": "999999"})
    client.post(f"/crm/approvals/{req.approval_id}/approve", json={}, headers=users.counsellor.headers)
    assert audit_rows(approval_id=req.approval_id, event_type="approval_execution_failed")


# ---------------------------------------------------------------- S9 opt-out
def test_s9_opt_out_through_the_api_stops_all_messages(client, users):
    with SessionLocal() as db:
        user = User(email=f"{uuid.uuid4().hex[:8]}@example.test", full_name="Quiet", role="student",
                    password_hash="x", is_active=True)
        db.add(user)
        db.commit()
        uid, email = user.id, user.email
    lead = crm.upsert_lead(LeadProfile(name="Quiet", email=email)).id
    crm.link_lead_to_user(lead, uid)
    headers = {"Authorization": f"Bearer {create_token(uid, 'student')}"}
    pending = sched.schedule_followup(lead, clock.to_ist(clock.now()), "hot_reminder")
    assert pending["ok"]

    assert client.patch(f"/crm/leads/{lead}/opt-out", headers=headers).status_code == 200
    assert audit_rows(event_type="api_action", tool_name="opt_out", lead_id=lead)
    assert sched.send_message("email", lead, "hello").error == "opted_out"
    outcome = next(o for o in followups.dispatch_due()["processed"] if o["followup_id"] == pending["followup_id"])
    assert outcome["detail"] == "opted_out"
    req = tools.request_approval("fee_waiver", {"lead_id": lead})
    res = client.post(f"/crm/approvals/{req.approval_id}/approve", json={}, headers=users.counsellor.headers)
    assert res.json()["outcome"]["notified"] is False
    assert sched.list_messages(lead) == []


# ---------------------------------------------------------------- audit
@pytest.mark.parametrize("sql", ["UPDATE audit_log SET actor = 'x'", "DELETE FROM audit_log", "TRUNCATE audit_log"])
def test_audit_log_is_append_only_in_the_database(users, sql):
    crm.log_event(actor="test", event_type="tool_call", tool_name=None, input=None, output=None,
                  reasoning_step=None, request_id=None)
    with SessionLocal() as db:
        with pytest.raises(DBAPIError, match="append-only"):
            db.execute(text(sql))
        db.rollback()


def test_audit_filters(client, users):
    lead = new_lead()
    tools.request_approval("fee_waiver", {"lead_id": lead})
    crm.log_event(actor="agent", event_type="plan", tool_name=None, input=None, output=None, reasoning_step=None,
                  request_id=None, lead_id=lead, session_id="sess-filter")
    crm.log_event(actor="agent", event_type="final", tool_name=None, input=None, output=None, reasoning_step=None,
                  request_id=None, lead_id=lead, session_id="sess-filter")
    h = users.counsellor.headers
    assert [r["event_type"] for r in client.get(f"/crm/audit?lead_id={lead}", headers=h).json()] == ["final", "plan"]
    assert [r["event_type"] for r in client.get("/crm/audit?session_id=sess-filter&type=plan", headers=h).json()] == ["plan"]
    assert len(client.get("/crm/audit?limit=1", headers=h).json()) == 1
    assert client.get("/crm/audit?from=2099-01-01T00:00:00Z", headers=h).json() == []


def test_funnel_counts(client, users):
    before = client.get("/crm/analytics/funnel", headers=users.counsellor.headers).json()
    new_lead()
    after = client.get("/crm/analytics/funnel", headers=users.counsellor.headers).json()
    assert after["total_leads"] == before["total_leads"] + 1
    assert after["by_status"]["new"] == before["by_status"].get("new", 0) + 1
    assert set(after) >= {"by_tier", "by_channel", "opted_out", "booked_sessions", "approvals"}


def test_book_endpoint_handles_unknown_lead_for_staff(client, users):
    res = client.post("/scheduling/book", json={"lead_id": 999999, "slot_id": "1"}, headers=users.counsellor.headers)
    assert res.status_code == 200 and res.json()["reason"] == "lead_not_found"


def test_interaction_actor_comes_from_the_token_not_the_request(client, users):
    lead = new_lead()
    res = client.post(f"/crm/leads/{lead}/interactions",
                      json={"actor": "agent", "channel": "web", "direction": "outbound", "message": "Called the student"},
                      headers=users.counsellor.headers)
    assert res.status_code == 201 and res.json()["actor"] == "counsellor"
    with SessionLocal() as db:
        assert db.scalars(select(Interaction).where(Interaction.lead_id == lead)).one().actor == "counsellor"
