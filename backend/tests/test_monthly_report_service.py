"""Tests for monthly_report_service core generate/retry logic (foroba#159)."""
from __future__ import annotations

import sqlite3

import pytest

import db
import jeli_service
import monthly_report_service as mrs

_USER = {"id": 1, "email": "u1@test.local", "name": "Test User", "tier": "premium", "audience": "base"}


@pytest.fixture
def conn():
    c = sqlite3.connect(":memory:")
    c.row_factory = sqlite3.Row
    db.init_schema(c)
    return c


async def _fake_gather_context(*args, **kwargs):
    return "Pazuru context", "Tsumi context"


async def _fake_generate_narrative(system_prompt, message):
    return "Generated narrative text."


async def _fake_generate_narrative_fails(system_prompt, message):
    raise ValueError("Ollama returned an empty response")


@pytest.mark.asyncio
async def test_generate_new_report_success(monkeypatch, conn):
    monkeypatch.setattr(jeli_service, "gather_context", _fake_gather_context)
    monkeypatch.setattr(jeli_service, "generate_narrative", _fake_generate_narrative)
    sent = []
    monkeypatch.setattr(mrs, "send_email", lambda to, subject, body: sent.append((to, subject, body)))

    row = await mrs.generate_new_report(conn, _USER, "2026-07", "manual", cookie="cookie123")

    assert row["status"] == "success"
    assert row["narrative_text"] == "Generated narrative text."
    assert row["attempt_count"] == 1
    assert len(sent) == 1
    assert sent[0][0] == "u1@test.local"


@pytest.mark.asyncio
async def test_generate_new_report_raises_quota_exceeded(monkeypatch, conn):
    monkeypatch.setattr(jeli_service, "gather_context", _fake_gather_context)
    monkeypatch.setattr(jeli_service, "generate_narrative", _fake_generate_narrative)
    monkeypatch.setattr(mrs, "send_email", lambda *a, **k: None)

    for _ in range(mrs.MONTHLY_REPORT_LIMIT):
        await mrs.generate_new_report(conn, _USER, "2026-07", "manual", cookie=None)

    with pytest.raises(mrs.QuotaExceededError):
        await mrs.generate_new_report(conn, _USER, "2026-07", "manual", cookie=None)


@pytest.mark.asyncio
async def test_generate_new_report_failure_path_sets_failed_status(monkeypatch, conn):
    monkeypatch.setattr(jeli_service, "gather_context", _fake_gather_context)
    monkeypatch.setattr(jeli_service, "generate_narrative", _fake_generate_narrative_fails)
    sent = []
    monkeypatch.setattr(mrs, "send_email", lambda to, subject, body: sent.append((to, subject, body)))

    row = await mrs.generate_new_report(conn, _USER, "2026-07", "manual", cookie=None)

    assert row["status"] == "failed"
    assert "empty response" in row["error_message"]
    assert len(sent) == 0


@pytest.mark.asyncio
async def test_retry_report_updates_same_row_without_consuming_quota(monkeypatch, conn):
    monkeypatch.setattr(jeli_service, "gather_context", _fake_gather_context)
    monkeypatch.setattr(jeli_service, "generate_narrative", _fake_generate_narrative_fails)
    monkeypatch.setattr(mrs, "send_email", lambda *a, **k: None)

    failed = await mrs.generate_new_report(conn, _USER, "2026-07", "manual", cookie=None)
    assert failed["status"] == "failed"
    count_before = db.count_monthly_reports_this_month(conn, user_id=_USER["id"], year_month="2026-07")

    monkeypatch.setattr(jeli_service, "generate_narrative", _fake_generate_narrative)
    retried = await mrs.retry_report(conn, _USER, failed["id"], cookie=None)

    assert retried["id"] == failed["id"]
    assert retried["status"] == "success"
    assert retried["attempt_count"] == 2
    count_after = db.count_monthly_reports_this_month(conn, user_id=_USER["id"], year_month="2026-07")
    assert count_after == count_before


@pytest.mark.asyncio
async def test_retry_report_raises_invalid_retry_if_not_failed(monkeypatch, conn):
    monkeypatch.setattr(jeli_service, "gather_context", _fake_gather_context)
    monkeypatch.setattr(jeli_service, "generate_narrative", _fake_generate_narrative)
    monkeypatch.setattr(mrs, "send_email", lambda *a, **k: None)

    success = await mrs.generate_new_report(conn, _USER, "2026-07", "manual", cookie=None)
    with pytest.raises(mrs.InvalidRetryError):
        await mrs.retry_report(conn, _USER, success["id"], cookie=None)


@pytest.mark.asyncio
async def test_retry_report_raises_not_found_for_wrong_user(monkeypatch, conn):
    monkeypatch.setattr(jeli_service, "gather_context", _fake_gather_context)
    monkeypatch.setattr(jeli_service, "generate_narrative", _fake_generate_narrative_fails)
    monkeypatch.setattr(mrs, "send_email", lambda *a, **k: None)

    failed = await mrs.generate_new_report(conn, _USER, "2026-07", "manual", cookie=None)
    other_user = {**_USER, "id": 2}
    with pytest.raises(mrs.ReportNotFoundError):
        await mrs.retry_report(conn, other_user, failed["id"], cookie=None)
