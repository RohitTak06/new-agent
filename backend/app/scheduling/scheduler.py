"""Background job that sends due follow-ups every few seconds (APScheduler 3.x).

Disabled with SCHEDULER_ENABLED=0 (tests call dispatch_due directly).
"""
from __future__ import annotations

import logging
import os

from apscheduler.schedulers.background import BackgroundScheduler

from app.scheduling.followups import dispatch_due

log = logging.getLogger(__name__)
INTERVAL_SECONDS = 10
_scheduler: BackgroundScheduler | None = None


def _tick() -> None:
    try:
        result = dispatch_due()
        if result["processed"]:
            log.info("follow-ups: %s sent, %s skipped", result["sent"], result["skipped"])
    except Exception:  # keep the job alive; the next tick retries
        log.exception("follow-up dispatch failed")


def start() -> None:
    """Start the job unless SCHEDULER_ENABLED=0. Idempotent."""
    global _scheduler
    if os.getenv("SCHEDULER_ENABLED", "1") == "0" or _scheduler is not None:
        return
    _scheduler = BackgroundScheduler(timezone="UTC")
    _scheduler.add_job(_tick, "interval", seconds=INTERVAL_SECONDS, id="dispatch_followups",
                       max_instances=1, coalesce=True)
    _scheduler.start()


def stop() -> None:
    global _scheduler
    if _scheduler is not None:
        _scheduler.shutdown(wait=False)
        _scheduler = None
