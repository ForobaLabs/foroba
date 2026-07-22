"""APScheduler — daily FX rate refresh (TI-D item 3 Plan 3, foroba#164).

Mirrors report_scheduler.py's start_X_scheduler() convention: one
BackgroundScheduler instance for this concern, started explicitly from
main.py's startup event.
"""
from __future__ import annotations

import logging

from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger

import fx_service
from auth.conn import get_conn

logger = logging.getLogger("foroba.fx_scheduler")


def _refresh_job() -> None:
    conn = get_conn()
    fx_service.refresh_latest_rates(conn)


def start_fx_scheduler() -> BackgroundScheduler:
    scheduler = BackgroundScheduler()
    scheduler.add_job(
        _refresh_job,
        trigger=CronTrigger(hour=4, minute=0),
        id="fx_rate_refresh",
        replace_existing=True,
        misfire_grace_time=3600,
    )
    scheduler.start()
    logger.info("FX rate refresh scheduler started (runs daily at 04:00).")
    return scheduler
