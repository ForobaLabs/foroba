"""Tests for backup_scheduler.py (TI-E, foroba#172). All dependencies (DB, JWT
signing, cross-app export, R2 upload) are mocked — no real network/credentials."""
from __future__ import annotations

import asyncio

import backup_scheduler as sched


def test_skips_when_offsite_backup_not_configured(monkeypatch):
    monkeypatch.setattr(sched.offsite_backup, "is_configured", lambda: False)
    called = {"export": False}
    monkeypatch.setattr(
        sched.backup_orchestrator, "export_suite",
        lambda *a, **kw: called.__setitem__("export", True),
    )

    asyncio.run(sched._run_daily_backup_async())

    assert called["export"] is False


def test_skips_when_no_admin_user_exists(monkeypatch):
    monkeypatch.setattr(sched.offsite_backup, "is_configured", lambda: True)
    monkeypatch.setattr(sched, "get_conn", lambda: object())
    monkeypatch.setattr(sched, "list_all_users", lambda conn: [
        {"id": 1, "is_admin": False, "tier": "free", "audience": "base"},
    ])
    called = {"export": False}
    monkeypatch.setattr(
        sched.backup_orchestrator, "export_suite",
        lambda *a, **kw: called.__setitem__("export", True),
    )

    asyncio.run(sched._run_daily_backup_async())

    assert called["export"] is False


def test_happy_path_exports_and_uploads(monkeypatch):
    monkeypatch.setattr(sched.offsite_backup, "is_configured", lambda: True)
    monkeypatch.setattr(sched, "get_conn", lambda: object())
    monkeypatch.setattr(sched, "list_all_users", lambda conn: [
        {"id": 1, "is_admin": False, "tier": "free", "audience": "base"},
        {"id": 2, "is_admin": True, "tier": "premium", "audience": "expert"},
    ])
    monkeypatch.setattr(sched.keys, "get_keypair", lambda settings: ("priv", "pub", "kid1"))

    captured_token_args: dict = {}

    def fake_create_token(user_id, private_key, ttl, *, tier, audience, is_admin, kid):
        captured_token_args.update(locals())
        return "fake-jwt"

    monkeypatch.setattr(sched, "create_token", fake_create_token)

    async def fake_export_suite(passphrase, cookie):
        assert cookie == "fake-jwt"
        return b"encrypted-archive"

    monkeypatch.setattr(sched.backup_orchestrator, "export_suite", fake_export_suite)

    uploaded: list[bytes] = []
    monkeypatch.setattr(
        sched.offsite_backup, "upload_backup",
        lambda data: uploaded.append(data) or "backups/suite-fake.bin",
    )

    asyncio.run(sched._run_daily_backup_async())

    assert captured_token_args["user_id"] == 2
    assert captured_token_args["is_admin"] is True
    assert uploaded == [b"encrypted-archive"]


def test_happy_path_logs_and_does_not_raise_on_export_failure(monkeypatch):
    monkeypatch.setattr(sched.offsite_backup, "is_configured", lambda: True)
    monkeypatch.setattr(sched, "get_conn", lambda: object())
    monkeypatch.setattr(sched, "list_all_users", lambda conn: [
        {"id": 2, "is_admin": True, "tier": "free", "audience": "base"},
    ])
    monkeypatch.setattr(sched.keys, "get_keypair", lambda settings: ("priv", "pub", "kid1"))
    monkeypatch.setattr(sched, "create_token", lambda *a, **kw: "fake-jwt")

    async def failing_export(passphrase, cookie):
        raise RuntimeError("pazuru unreachable")

    monkeypatch.setattr(sched.backup_orchestrator, "export_suite", failing_export)

    asyncio.run(sched._run_daily_backup_async())  # must not raise
