"""Shared pytest setup.

Tests run against a throwaway `admissions_test` database in the same Postgres
container, recreated and migrated once per run, so the seeded dev data is
never touched. The env vars are set here, before any `app` import, because
app modules read them at import time.
"""
import os
from pathlib import Path

import psycopg
import pytest
from dotenv import load_dotenv

load_dotenv()

_DEV_URL = os.environ.get(
    "DATABASE_URL", "postgresql+psycopg://buildathon:buildathon@localhost:5432/admissions"
)
_BASE, _, _ = _DEV_URL.rpartition("/")
TEST_DB = "admissions_test"
os.environ["DATABASE_URL"] = f"{_BASE}/{TEST_DB}"
os.environ["USE_REAL_INTEL"] = "1"
os.environ["USE_REAL_CRM"] = "1"
os.environ["USE_REAL_SCHEDULING"] = "1"
os.environ["SCHEDULER_ENABLED"] = "0"   # tests call dispatch_due directly
os.environ["JWT_SECRET"] = "test-only-secret-" + "x" * 32
os.environ["ENABLE_FAULT_INJECTION"] = "1"
LIVE_LLM = {k: os.environ.get(k, "") for k in ("LLM_API_KEY", "LLM_MODEL")}     # only @pytest.mark.live uses these
os.environ["LLM_API_KEY"] = ""     # no test reaches Gemini by accident
os.environ["LLM_MODEL"] = ""


def _recreate_test_db() -> None:
    admin_url = _BASE.replace("postgresql+psycopg://", "postgresql://") + "/postgres"
    with psycopg.connect(admin_url, autocommit=True) as conn:
        conn.execute(f"DROP DATABASE IF EXISTS {TEST_DB} WITH (FORCE)")
        conn.execute(f"CREATE DATABASE {TEST_DB}")


@pytest.fixture(scope="session", autouse=True)
def test_database():
    """Fresh, fully migrated test database for the whole run."""
    from alembic import command
    from alembic.config import Config

    _recreate_test_db()
    ini = Path(__file__).resolve().parents[1] / "app" / "crm" / "db" / "alembic.ini"
    command.upgrade(Config(str(ini)), "head")
    yield


@pytest.fixture(scope="session")
def users(test_database):
    """Test accounts: admin, counsellor and two students with their own leads, each with auth headers."""
    from types import SimpleNamespace

    from app.crm.auth import create_token
    from app.crm.db.base import SessionLocal
    from app.crm.db.models import Lead, User
    from app.crm.service import hash_password

    accounts = {}
    with SessionLocal() as db:
        for name, role in [("admin", "admin"), ("counsellor", "counsellor"),
                           ("student", "student"), ("other_student", "student")]:
            email = f"{name}@example.test"
            user = User(email=email, full_name=name.title(), role=role,
                        password_hash=hash_password(f"{name}-password"), is_active=True)
            db.add(user)
            db.flush()
            lead_id = None
            if role == "student":
                lead = Lead(user_id=user.id, name=name.title(), email=email, channel="web", status="new")
                db.add(lead)
                db.flush()
                lead_id = lead.id
            accounts[name] = SimpleNamespace(id=user.id, email=email, role=role, password=f"{name}-password",
                                             lead_id=lead_id,
                                             headers={"Authorization": f"Bearer {create_token(user.id, role)}"})
        db.commit()
    return SimpleNamespace(**accounts)
