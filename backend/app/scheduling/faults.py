"""Fault injection for the failure demo (SPEC S5): make the next N calendar calls fail.

Only reachable through an admin endpoint that is off unless ENABLE_FAULT_INJECTION=1.
"""
from __future__ import annotations

import threading

TARGETS = {"book_slot", "get_slots"}
_lock = threading.Lock()
_remaining: dict[str, int] = {}


class CalendarUnavailable(Exception):
    """Injected failure, standing in for a calendar outage."""


def arm(target: str, failures: int) -> None:
    """Make the next `failures` calls to `target` raise. 0 clears it."""
    with _lock:
        _remaining[target] = failures


def check(target: str) -> None:
    """Called at the start of each calendar operation."""
    with _lock:
        left = _remaining.get(target, 0)
        if left <= 0:
            return
        _remaining[target] = left - 1
    raise CalendarUnavailable(f"calendar unavailable ({target})")
