"""APScheduler — daily offsite backup upload (TI-E, foroba#172).

Runs every day at 12:00 local time (noon, not 04:00 — the host machine is not
guaranteed to be powered on overnight). Mints an internal admin JWT (same
`create_token` call already used by `report_scheduler.py`) so
`backup_orchestrator.export_suite()`'s existing httpx calls to Pazuru/Tsumi's
`/admin/backup/export` authenticate normally, then uploads the resulting
encrypted archive to R2. No-ops (logs and returns) when offsite_backup is
unconfigured or no admin user exists yet.
"""
from __future__ import annotations

import asyncio
import logging

from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger

import backup_orchestrator
import offsite_backup
from auth import keys
from auth.conn import get_conn
from auth.repository import list_all_users
from auth.security import create_token
from config import settings

logger = logging.getLogger("foroba.backup_scheduler")


async def _run_daily_backup_async() -> None:
    if not offsite_backup.is_configured():
        logger.info("Offsite backup scheduler: R2 not configured, skipping run.")
        return

    conn = get_conn()
    admin = next((u for u in list_all_users(conn) if u.get("is_admin")), None)
    if admin is None:
        logger.warning("Offsite backup scheduler: no admin user found, skipping run.")
        return

    private_key, _, kid = keys.get_keypair(settings)
    token = create_token(
        admin["id"], private_key, settings.jwt_ttl_minutes,
        tier=admin["tier"], audience=admin["audience"], is_admin=True, kid=kid,
    )

    try:
        archive = await backup_orchestrator.export_suite(
            settings.backup_encryption_passphrase, cookie=token,
        )
        key = offsite_backup.upload_backup(archive)
        logger.info("Offsite backup scheduler: uploaded %s", key)
    except Exception:
        logger.exception("Offsite backup scheduler: run failed")


def run_daily_backup() -> None:
    """Sync entry point for APScheduler (thread-based, not asyncio-native)."""
    asyncio.run(_run_daily_backup_async())


def start_backup_scheduler() -> BackgroundScheduler:
    scheduler = BackgroundScheduler()
    scheduler.add_job(
        run_daily_backup,
        trigger=CronTrigger(hour=12, minute=0),
        id="offsite_backup",
        replace_existing=True,
        misfire_grace_time=3600,
    )
    scheduler.start()
    logger.info("Offsite backup scheduler started (runs daily at 12:00).")
    return scheduler
