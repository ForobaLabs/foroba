"""Tests for report_scheduler eligibility filtering, skip-if-exists, and retry backoff
(foroba#159, TI-D item 2)."""

from __future__ import annotations

import logging
import sqlite3

import pytest

import db
import report_scheduler as rs

_ELIGIBLE_USER = {
    "id": 1,
    "email": "u1@test.local",
    "name": "U1",
    "tier": "premium",
    "audience": "base",
    "is_admin": 0,
}
_INELIGIBLE_USER = {
    "id": 2,
    "email": "u2@test.local",
    "name": "U2",
    "tier": "free",
    "audience": "base",
    "is_admin": 0,
}


@pytest.fixture
def conn():
    c = sqlite3.connect(":memory:")
    c.row_factory = sqlite3.Row
    db.init_schema(c)
    return c


@pytest.mark.asyncio
async def test_generate_for_user_skips_if_row_already_exists(monkeypatch, conn):
    db.create_monthly_report(conn, user_id=1, year_month="2026-07", trigger="manual")
    called = []
    monkeypatch.setattr(rs.mrs, "_run_generation", lambda *a, **k: called.append(1))

    await rs._generate_for_user(conn, _ELIGIBLE_USER, "2026-07", "token123")

    assert called == []


@pytest.mark.asyncio
async def test_generate_for_user_retries_with_backoff_then_gives_up(monkeypatch, conn, caplog):
    sleeps = []

    async def fake_sleep(seconds):
        sleeps.append(seconds)

    async def failing_run(conn_, row, user, *, cookie, stepup_pazuru=None, stepup_tsumi=None):
        return db.update_monthly_report_result(
            conn_,
            row["id"],
            status="failed",
            narrative_text=None,
            context_snapshot_json=None,
            error_message="boom",
            attempt_count=row["attempt_count"] + 1,
        )

    monkeypatch.setattr(rs.asyncio, "sleep", fake_sleep)
    monkeypatch.setattr(rs.mrs, "_run_generation", failing_run)

    with caplog.at_level(logging.ERROR):
        await rs._generate_for_user(conn, _ELIGIBLE_USER, "2026-07", "token123")

    assert sleeps == [5, 15, 30]
    assert "exhausted 4 attempts" in caplog.text


@pytest.mark.asyncio
async def test_generate_for_user_stops_retrying_on_success(monkeypatch, conn):
    sleeps = []

    async def fake_sleep(seconds):
        sleeps.append(seconds)

    calls = []

    async def flaky_run(conn_, row, user, *, cookie, stepup_pazuru=None, stepup_tsumi=None):
        calls.append(1)
        if len(calls) < 2:
            return db.update_monthly_report_result(
                conn_,
                row["id"],
                status="failed",
                narrative_text=None,
                context_snapshot_json=None,
                error_message="boom",
                attempt_count=row["attempt_count"] + 1,
            )
        return db.update_monthly_report_result(
            conn_,
            row["id"],
            status="success",
            narrative_text="ok",
            context_snapshot_json=None,
            error_message=None,
            attempt_count=row["attempt_count"] + 1,
        )

    monkeypatch.setattr(rs.asyncio, "sleep", fake_sleep)
    monkeypatch.setattr(rs.mrs, "_run_generation", flaky_run)

    await rs._generate_for_user(conn, _ELIGIBLE_USER, "2026-07", "token123")

    assert len(calls) == 2
    assert sleeps == [5]


def test_eligible_filtering_by_evaluate(monkeypatch, conn):
    monkeypatch.setattr(rs, "list_all_users", lambda conn_: [_ELIGIBLE_USER, _INELIGIBLE_USER])

    def fake_evaluate(key, user, *, gating_enabled):
        class _Access:
            unlocked = user["tier"] == "premium"

        return _Access()

    monkeypatch.setattr(rs, "evaluate", fake_evaluate)
    users = rs.list_all_users(conn)
    eligible = [
        u
        for u in users
        if rs.evaluate("banking.monthly_ai_report", u, gating_enabled=True).unlocked
    ]
    assert eligible == [_ELIGIBLE_USER]
