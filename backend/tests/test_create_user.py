"""Staff accounts come from the server's command line, never from self-registration."""
import uuid

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select

from app.crm import create_user
from app.crm.create_user import StaffAccountError, create_staff
from app.crm.db.base import SessionLocal
from app.crm.db.models import AuditLog, User
from app.main import app
from app.scheduling import service as sched
from app.scheduling.models import Counsellor, SlotRow


@pytest.fixture
def client():
    return TestClient(app)


def email() -> str:
    return f"staff.{uuid.uuid4().hex[:8]}@jklu.example"


def test_a_new_counsellor_can_log_in_and_be_booked(client, users):
    address = email()
    result = create_staff(address, "Ms. Kavya Test", "counsellor", "counsel-pass-1")
    assert result["role"] == "counsellor" and result["slots_opened"] > 0

    res = client.post("/crm/auth/login", data={"username": address, "password": "counsel-pass-1"})
    assert res.status_code == 200 and res.json()["role"] == "counsellor"
    headers = {"Authorization": f"Bearer {res.json()['access_token']}"}
    assert client.get("/crm/leads", headers=headers).status_code == 200          # a counsellor's screens
    assert client.get("/crm/audit", headers=headers).status_code == 403          # not an admin's

    with SessionLocal() as db:
        c = db.scalars(select(Counsellor).where(Counsellor.user_id == result["user_id"])).one()
    assert c.name == "Ms. Kavya Test"
    assert "Ms. Kavya Test" in {x.name for x in sched.get_counsellors()}
    with SessionLocal() as db:
        theirs = db.scalars(select(SlotRow).where(SlotRow.counsellor_id == c.id)).all()
    assert len(theirs) == result["slots_opened"] and all(s.status == "free" for s in theirs)


def test_a_new_admin_gets_the_admin_screens(client):
    address = email()
    create_staff(address, "Admin Test", "admin", "admin-pass-12")
    token = client.post("/crm/auth/login", data={"username": address, "password": "admin-pass-12"}).json()["access_token"]
    assert client.get("/crm/audit", headers={"Authorization": f"Bearer {token}"}).status_code == 200
    with SessionLocal() as db:
        user_id = db.scalars(select(User.id).where(User.email == address)).one()
        assert db.scalars(select(Counsellor).where(Counsellor.user_id == user_id)).first() is None   # not bookable


def test_the_password_is_stored_hashed_and_never_logged():
    address = email()
    create_staff(address, "Hash Test", "counsellor", "secret-pass-99")
    with SessionLocal() as db:
        user = db.scalars(select(User).where(User.email == address)).one()
        row = db.scalars(select(AuditLog).where(AuditLog.event_type == "create_user",
                                                AuditLog.tool_name == "crm.create_user")
                         .order_by(AuditLog.id.desc())).first()
    assert user.password_hash != "secret-pass-99" and "secret-pass-99" not in user.password_hash
    assert row.input == {"email": address, "name": "Hash Test", "role": "counsellor"}
    assert "secret-pass-99" not in str(row.output)


@pytest.mark.parametrize("args,why", [
    ({"role": "student"}, "Students register in the app"),
    ({"email": "not-an-email"}, "valid email"),
    ({"name": "   "}, "full name"),
    ({"password": "short"}, "at least 8"),
])
def test_bad_details_are_refused(args, why):
    details = {"email": email(), "name": "Someone", "role": "counsellor", "password": "long-enough-1", **args}
    with pytest.raises(StaffAccountError, match=why):
        create_staff(**details)


def test_an_email_in_use_is_refused_in_any_case(users):
    with pytest.raises(StaffAccountError, match="already exists"):
        create_staff(users.student.email.upper(), "Copy", "counsellor", "long-enough-1")


def test_the_command_line_asks_for_the_password_twice(monkeypatch, capsys):
    answers = iter(["cli-pass-123", "cli-pass-123"])
    monkeypatch.setattr(create_user.getpass, "getpass", lambda prompt="": next(answers))
    address = email()
    assert create_user.main(["--role", "counsellor", "--email", address, "--name", "Mr. CLI Test"]) == 0
    assert "Created counsellor Mr. CLI Test" in capsys.readouterr().out


def test_the_command_line_stops_on_a_mismatch(monkeypatch, capsys):
    answers = iter(["cli-pass-123", "different-456"])
    monkeypatch.setattr(create_user.getpass, "getpass", lambda prompt="": next(answers))
    address = email()
    assert create_user.main(["--role", "admin", "--email", address, "--name", "Mismatch"]) == 1
    assert "don't match" in capsys.readouterr().err
    with SessionLocal() as db:
        assert db.scalars(select(User).where(User.email == address)).first() is None


def test_registration_still_cannot_make_staff(client):
    form = {"first_name": "Sneaky", "last_name": "Staff", "email": email(), "phone": "9876543210", "state": "Delhi",
            "city": "Delhi", "course": "BBA (Fintech)", "password": "long-enough-1", "consent": True, "role": "admin"}
    res = client.post("/crm/auth/register", json=form)
    assert res.status_code == 201 and res.json()["role"] == "student"
