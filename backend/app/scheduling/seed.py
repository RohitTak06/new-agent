"""Seed counsellors and free slots for the next 7 virtual days. Synthetic data only.

    python -m app.scheduling.seed

Idempotent: counsellors are created once (linked to the CRM's counsellor users
when they exist), and re-running tops up slots for days not yet covered, so it
still works after the virtual clock has been advanced.
"""
from __future__ import annotations

from datetime import datetime, time, timedelta

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert

from app.crm.db.base import SessionLocal
from app.crm.db.models import User
from app.scheduling import clock
from app.scheduling.models import Counsellor, SlotRow

DAYS = 7
SLOT_MINUTES = 30
HOURS = [(10, 13), (14, 17)]          # IST working blocks, lunch 13:00-14:00
WORKDAYS = range(0, 6)                # Monday-Saturday
FALLBACK_NAMES = ["Dr. Neha Sharma", "Mr. Arjun Verma", "Ms. Priya Nair"]


def ensure_counsellors() -> list[int]:
    """Return active counsellor ids, creating them from counsellor users (or fallback names) once."""
    with SessionLocal() as db:
        if not db.scalars(select(Counsellor.id)).first():
            users = db.scalars(select(User).where(User.role == "counsellor").order_by(User.id)).all()
            db.add_all([Counsellor(user_id=u.id, name=u.full_name) for u in users]
                       or [Counsellor(name=n) for n in FALLBACK_NAMES])
            db.commit()
        return list(db.scalars(select(Counsellor.id).where(Counsellor.active.is_(True)).order_by(Counsellor.id)))


def slot_times(start_day, days: int = DAYS):
    """(start, end) datetimes in IST for each working slot over `days` days from `start_day`."""
    for d in range(days):
        day = start_day + timedelta(days=d)
        if day.weekday() not in WORKDAYS:
            continue
        for first, last in HOURS:
            t = datetime.combine(day, time(first), tzinfo=clock.IST)
            while t.hour < last:
                yield t, t + timedelta(minutes=SLOT_MINUTES)
                t += timedelta(minutes=SLOT_MINUTES)


def seed_slots(days: int = DAYS) -> int:
    """Insert missing future slots for every counsellor. Returns how many were added."""
    counsellors = ensure_counsellors()
    now = clock.now()
    rows = [{"counsellor_id": c, "start_at": s, "end_at": e}
            for s, e in slot_times(now.astimezone(clock.IST).date(), days) if s > now
            for c in counsellors]
    if not rows:
        return 0
    with SessionLocal() as db:
        res = db.execute(insert(SlotRow).values(rows)
                         .on_conflict_do_nothing(constraint="uq_slots_counsellor_start")
                         .returning(SlotRow.id))
        added = len(res.all())
        db.commit()
    return added


if __name__ == "__main__":
    n = seed_slots()
    print(f"[seed] counsellors ready; {n} new slots for the next {DAYS} virtual days "
          f"(now {clock.to_ist(clock.now())}).")
