"""Create a staff account (counsellor or admin) from the command line.

Students register themselves in the app; staff never can. An admin with access to the
server creates each staff account here instead:

    python -m app.crm.create_user --role counsellor --email kavya.rao@jklu.example --name "Ms. Kavya Rao"

The password is asked for twice and never shown, stored only as a hash, and never logged.
A counsellor is also added to the booking calendar with free sessions for the next week,
so students can book them straight away. Every account created is written to the audit log.
"""
from __future__ import annotations

import argparse
import getpass
import sys

from sqlalchemy import func, select
from sqlalchemy.dialects.postgresql import insert

from app.crm.auth import STAFF
from app.crm.db.base import SessionLocal
from app.crm.db.models import User
from app.crm.registration import _EMAIL, MIN_PASSWORD
from app.crm.service import hash_password, log_event
from app.scheduling import clock
from app.scheduling.models import Counsellor, SlotRow
from app.scheduling.seed import DAYS, slot_times


class StaffAccountError(ValueError):
    """The account can't be created as asked; the message says why."""


def _check(email: str, name: str, role: str, password: str) -> tuple[str, str]:
    email, name = email.strip().lower(), name.strip()
    if role not in STAFF:
        raise StaffAccountError(f"Role must be one of: {', '.join(STAFF)}. Students register in the app.")
    if not _EMAIL.match(email):
        raise StaffAccountError("Enter a valid email address")
    if not name:
        raise StaffAccountError("Enter the person's full name")
    if len(password) < MIN_PASSWORD:
        raise StaffAccountError(f"The password must be at least {MIN_PASSWORD} characters")
    return email, name


def _open_slots(counsellor_id: int) -> int:
    """Free sessions for the next week for one counsellor, so students can book them at once."""
    now = clock.now()
    rows = [{"counsellor_id": counsellor_id, "start_at": s, "end_at": e}
            for s, e in slot_times(now.astimezone(clock.IST).date(), DAYS) if s > now]
    if not rows:
        return 0
    with SessionLocal() as db:
        added = db.execute(insert(SlotRow).values(rows)
                           .on_conflict_do_nothing(constraint="uq_slots_counsellor_start").returning(SlotRow.id)).all()
        db.commit()
    return len(added)


def create_staff(email: str, name: str, role: str, password: str) -> dict:
    """Create one staff account. Raises StaffAccountError if the details are invalid or the email is taken."""
    email, name = _check(email, name, role, password)
    with SessionLocal() as db:
        if db.scalar(select(User.id).where(func.lower(User.email) == email)) is not None:
            raise StaffAccountError("An account with this email already exists")
        user = User(email=email, full_name=name, role=role, password_hash=hash_password(password), is_active=True)
        db.add(user)
        db.flush()
        counsellor_id = None
        if role == "counsellor":
            counsellor = Counsellor(user_id=user.id, name=name)
            db.add(counsellor)
            db.flush()
            counsellor_id = counsellor.id
        db.commit()
        user_id = user.id
    slots = _open_slots(counsellor_id) if counsellor_id is not None else 0
    result = {"user_id": user_id, "email": email, "name": name, "role": role,
              "counsellor_id": counsellor_id, "slots_opened": slots}
    log_event(actor="create_user (server command line)", event_type="create_user", tool_name="crm.create_user",
              input={"email": email, "name": name, "role": role}, output=result, reasoning_step=None, request_id=None)
    return result


def _ask_password() -> str:
    first = getpass.getpass("Password (at least 8 characters, not shown): ")
    if first != getpass.getpass("Type it again: "):
        raise StaffAccountError("The two passwords don't match")
    return first


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Create a counsellor or admin account. Students register in the app.")
    parser.add_argument("--role", required=True, choices=STAFF)
    parser.add_argument("--email", required=True)
    parser.add_argument("--name", required=True, help='Full name as students will see it, e.g. "Ms. Kavya Rao"')
    args = parser.parse_args(argv)
    try:
        _check(args.email, args.name, args.role, "x" * MIN_PASSWORD)    # fail fast, before asking for a password
        result = create_staff(args.email, args.name, args.role, _ask_password())
    except StaffAccountError as err:
        print(f"Not created: {err}", file=sys.stderr)
        return 1
    extra = f", with {result['slots_opened']} free sessions this week" if result["role"] == "counsellor" else ""
    print(f"Created {result['role']} {result['name']} <{result['email']}>{extra}. They can log in on the Log in tab now.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
