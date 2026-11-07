"""One command for the demo: database, migrations, seed data, API and frontend.

    python scripts/demo.py            # start everything; seeds an empty database
    python scripts/demo.py --reset    # ERASES the local 'admissions' database first, then the same
    python scripts/demo.py --reset --no-start     # rebuild only

Run from backend/ with its virtualenv active. Ctrl+C stops the API and frontend.
"""
from __future__ import annotations

import argparse
import os
import shutil
import subprocess
import sys
import time
from pathlib import Path

import psycopg
from dotenv import load_dotenv

BACKEND = Path(__file__).resolve().parents[1]
ROOT = BACKEND.parent
FRONTEND = ROOT / "frontend"
DEFAULT_URL = "postgresql+psycopg://buildathon:buildathon@localhost:5432/admissions"


def fail(message: str) -> None:
    raise SystemExit(f"\n[demo] {message}")


def start_database() -> None:
    print("[demo] Starting the database...")
    if subprocess.run(["docker", "compose", "up", "-d", "db"], cwd=ROOT, capture_output=True).returncode != 0:
        fail("Docker couldn't start the database. Is Docker Desktop running?")


def admin_url(database_url: str) -> str:
    base, _, _ = database_url.replace("postgresql+psycopg://", "postgresql://").rpartition("/")
    return f"{base}/postgres"


def wait_for_database(database_url: str, seconds: int = 60) -> None:
    deadline = time.monotonic() + seconds
    while True:
        try:
            with psycopg.connect(admin_url(database_url), connect_timeout=3):
                return
        except psycopg.OperationalError:
            if time.monotonic() > deadline:
                fail(f"The database wasn't ready after {seconds} seconds.")
            time.sleep(1)


def erase_database(database_url: str) -> None:
    from app.demo_seed import assert_safe_to_reset

    assert_safe_to_reset(database_url)
    print("[demo] Erasing the local 'admissions' database...")
    with psycopg.connect(admin_url(database_url), autocommit=True) as conn:
        conn.execute("DROP DATABASE IF EXISTS admissions WITH (FORCE)")
        conn.execute("CREATE DATABASE admissions")


def migrate() -> None:
    from alembic import command
    from alembic.config import Config

    print("[demo] Applying migrations...")
    command.upgrade(Config(str(BACKEND / "app" / "crm" / "db" / "alembic.ini")), "head")


def seed_if_empty() -> None:
    from sqlalchemy import func, select

    from app.crm.db.base import SessionLocal
    from app.crm.db.models import User
    from app.crm.seed import run_seed
    from app.demo_seed import score_seed_leads, stage_demo

    with SessionLocal() as db:
        if db.scalar(select(func.count(User.id))):
            print("[demo] Data already present, so nothing was seeded. Use --reset for a clean start.")
            return

    run_seed()
    print(f"[demo] Scored {score_seed_leads()} leads.")
    staged = stage_demo()
    slot = staged["clash_slot"]
    print("\n[demo] Ready. For the booking clash, the student types:")
    print(f'    Please book slot {slot.slot_id} with {slot.counsellor}.')
    print(f"    ({slot.start} IST; already held by another student)\n")


def stop(process: subprocess.Popen) -> None:
    if process.poll() is not None:
        return
    if os.name == "nt":       # npm starts child processes, and terminate() would leave them running
        subprocess.run(["taskkill", "/PID", str(process.pid), "/T", "/F"], capture_output=True)
    else:
        process.terminate()


def start_servers() -> None:
    npm = shutil.which("npm")
    if npm is None:
        fail("npm wasn't found. Install Node.js 18 or newer.")
    if not (FRONTEND / "node_modules").exists():
        print("[demo] Installing frontend packages...")
        subprocess.run([npm, "ci"], cwd=FRONTEND, check=True)

    api = subprocess.Popen([sys.executable, "-m", "uvicorn", "app.main:app", "--port", "8000"], cwd=BACKEND,
                           env={**os.environ, "ENABLE_FAULT_INJECTION": "1"})
    web = subprocess.Popen([npm, "run", "dev"], cwd=FRONTEND)
    print("\n[demo] Frontend: http://localhost:5173    API docs: http://localhost:8000/docs")
    print("[demo] Press Ctrl+C to stop.\n")
    try:
        while api.poll() is None and web.poll() is None:
            time.sleep(1)
        fail("A server stopped unexpectedly. See the output above.")
    except KeyboardInterrupt:
        print("\n[demo] Stopping...")
    finally:
        stop(api)
        stop(web)


def main() -> None:
    parser = argparse.ArgumentParser(description="Set up and start the demo.")
    parser.add_argument("--reset", action="store_true", help="erase the local 'admissions' database first")
    parser.add_argument("--no-start", action="store_true", help="set up the data but don't start the servers")
    args = parser.parse_args()

    if not (ROOT / ".env").exists():
        fail("No .env file. Copy .env.example to .env and fill it in.")
    load_dotenv(ROOT / ".env")
    os.chdir(BACKEND)
    sys.path.insert(0, str(BACKEND))
    database_url = os.environ.get("DATABASE_URL", DEFAULT_URL)

    start_database()
    wait_for_database(database_url)
    if args.reset:
        erase_database(database_url)
    migrate()
    seed_if_empty()
    if not args.no_start:
        start_servers()


if __name__ == "__main__":
    main()
