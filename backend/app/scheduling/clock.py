"""Virtual clock: real UTC time plus an offset stored in `virtual_clock` (row id=1).

Everything time-based in scheduling (slots in the past, follow-ups due, message
timestamps) uses `now()`, so the demo can fast-forward with `advance()`.
"""
from __future__ import annotations

from datetime import date, datetime, time, timedelta, timezone

from sqlalchemy import update

from app.crm.db.base import SessionLocal
from app.scheduling.models import VirtualClock

IST = timezone(timedelta(hours=5, minutes=30))
MAX_ADVANCE_HOURS = 720


def offset_seconds() -> int:
    """Current offset of the virtual clock from real time."""
    with SessionLocal() as db:
        row = db.get(VirtualClock, 1)
        return row.offset_seconds if row else 0


def now() -> datetime:
    """Current virtual time (UTC, timezone-aware)."""
    return datetime.now(timezone.utc) + timedelta(seconds=offset_seconds())


def advance(hours: float) -> datetime:
    """Move the clock forward by `hours` (0 < hours <= 720). Returns the new virtual time."""
    if not 0 < hours <= MAX_ADVANCE_HOURS:
        raise ValueError(f"hours must be > 0 and <= {MAX_ADVANCE_HOURS}")
    with SessionLocal() as db:
        db.execute(update(VirtualClock).where(VirtualClock.id == 1)
                   .values(offset_seconds=VirtualClock.offset_seconds + int(hours * 3600)))
        db.commit()
    return now()


def to_ist(dt: datetime) -> str:
    """ISO string in IST, e.g. 2026-11-04T10:00:00+05:30."""
    return dt.astimezone(IST).isoformat(timespec="seconds")


def parse(value: str, end_of_day: bool = False) -> datetime:
    """Parse an ISO date or datetime. Dates are whole IST days; naive datetimes are IST.

    With end_of_day=True a plain date means the end of that day (exclusive bound).
    """
    value = value.strip()
    if len(value) == 10:
        d = date.fromisoformat(value)
        start = datetime.combine(d, time.min, tzinfo=IST)
        return start + timedelta(days=1) if end_of_day else start
    dt = datetime.fromisoformat(value.replace("Z", "+00:00"))
    return dt if dt.tzinfo else dt.replace(tzinfo=IST)
