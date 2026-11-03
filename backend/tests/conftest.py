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
os.environ["USE_REAL_SCHEDULING"] = "0"


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
