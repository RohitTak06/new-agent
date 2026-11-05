"""In-memory sliding-window rate limits: enough for one API process, reset on restart.

Login is limited on failures, so a known password never gets locked out. Chat is limited
on every request, because it is open without login and each turn spends model quota.
"""
from __future__ import annotations

import os
import threading
import time
from collections import defaultdict, deque

from fastapi import HTTPException, Request

from app.crm.service import log_event


class SlidingWindow:
    """At most `limit` hits per key within the last `seconds`."""

    def __init__(self, limit: int, seconds: float):
        self.limit = limit
        self.seconds = seconds
        self._hits: dict[str, deque[float]] = defaultdict(deque)
        self._lock = threading.Lock()

    def _current(self, key: str) -> deque[float]:
        hits = self._hits[key]
        cutoff = time.monotonic() - self.seconds
        while hits and hits[0] <= cutoff:
            hits.popleft()
        return hits

    def blocked(self, key: str) -> bool:
        with self._lock:
            return len(self._current(key)) >= self.limit

    def hit(self, key: str) -> None:
        with self._lock:
            self._current(key).append(time.monotonic())

    def reset(self, key: str | None = None) -> None:
        with self._lock:
            if key is None:
                self._hits.clear()
            else:
                self._hits.pop(key, None)


login_failures = SlidingWindow(limit=5, seconds=300)
chat_requests = SlidingWindow(limit=30, seconds=60)


def enabled() -> bool:
    return os.getenv("RATE_LIMITS_ENABLED", "1") != "0"


def client_ip(request: Request) -> str:
    return request.client.host if request.client else "unknown"


def refuse(window: SlidingWindow, request: Request, what: str) -> HTTPException:
    """Audit a refused request and return the 429 to raise."""
    log_event(actor=client_ip(request), event_type="rate_limited", tool_name=request.url.path,
              input={"method": request.method}, output=None, reasoning_step=what, request_id=None)
    return HTTPException(status_code=429, detail=f"Too many {what}. Please wait a few minutes and try again.",
                         headers={"Retry-After": str(int(window.seconds))})
