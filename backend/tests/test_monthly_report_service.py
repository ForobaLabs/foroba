"""Tests for monthly_report_service core generate/retry logic (foroba#159, foroba#281).

Plan AC (foroba#281) split generation into a fast synchronous kick-off
(start_new_report/start_retry) and a backgrounded run (run_generation_in_background
-> _run_generation), so nginx's 60s proxy_read_timeout no longer 504s a real ~300s
LLM call. These tests cover the kick-off functions directly (fast, in-memory conn)
and _run_generation directly (the actual generation logic, unchanged in behavior
other than the empty-error-message fix); run_generation_in_background's own
conn-sourcing is covered separately since it calls the real get_conn().
"""

from __future__ import annotations

import sqlite3

import pytest

import db
import jeli_service
import monthly_report_service as mrs

_USER = {
    "id": 1,
    "email": "u1@test.local",
    "name": "Test User",
    "tier": "premium",
    "audience": "base",
}


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


class _BlankStrException(Exception):
    """Mirrors httpx.ReadTimeout: a real exception whose str() is empty."""

    def __str__(self):
        return ""


async def _fake_generate_narrative_blank_error(system_prompt, message):
    raise _BlankStrException()


def test_start_new_report_creates_generating_row(conn):
    row = mrs.start_new_report(conn, _USER, "2026-07", "manual")

    assert row["status"] == "generating"
    assert row["year_month"] == "2026-07"
    assert row["attempt_count"] == 0


def test_start_new_report_raises_quota_exceeded(conn):
    for _ in range(mrs.MONTHLY_REPORT_LIMIT):
        mrs.start_new_report(conn, _USER, "2026-07", "manual")

    with pytest.raises(mrs.QuotaExceededError):
        mrs.start_new_report(conn, _USER, "2026-07", "manual")


def test_start_retry_flips_failed_row_to_generating_and_clears_error(conn):
    row = mrs.start_new_report(conn, _USER, "2026-07", "manual")
    db.update_monthly_report_result(
        conn,
        row["id"],
        status="failed",
        narrative_text=None,
        context_snapshot_json=None,
        error_message="boom",
        attempt_count=1,
    )

    retried = mrs.start_retry(conn, _USER, row["id"])

    assert retried["status"] == "generating"
    assert retried["error_message"] is None
    assert retried["attempt_count"] == 1


def test_start_retry_raises_invalid_retry_if_not_failed(conn):
    row = mrs.start_new_report(conn, _USER, "2026-07", "manual")

    with pytest.raises(mrs.InvalidRetryError):
        mrs.start_retry(conn, _USER, row["id"])


def test_start_retry_raises_not_found_for_wrong_user(conn):
    row = mrs.start_new_report(conn, _USER, "2026-07", "manual")
    other_user = {**_USER, "id": 2}

    with pytest.raises(mrs.ReportNotFoundError):
        mrs.start_retry(conn, other_user, row["id"])


@pytest.mark.asyncio
async def test_run_generation_success_updates_row(monkeypatch, conn):
    monkeypatch.setattr(jeli_service, "gather_context", _fake_gather_context)
    monkeypatch.setattr(jeli_service, "generate_narrative", _fake_generate_narrative)
    sent = []
    monkeypatch.setattr(
        mrs, "send_email", lambda to, subject, body: sent.append((to, subject, body))
    )
    row = mrs.start_new_report(conn, _USER, "2026-07", "manual")

    updated = await mrs._run_generation(conn, row, _USER, cookie="cookie123")

    assert updated["status"] == "success"
    assert updated["narrative_text"] == "Generated narrative text."
    assert updated["attempt_count"] == 1
    assert len(sent) == 1
    assert sent[0][0] == "u1@test.local"


@pytest.mark.asyncio
async def test_run_generation_failure_path_sets_failed_status(monkeypatch, conn):
    monkeypatch.setattr(jeli_service, "gather_context", _fake_gather_context)
    monkeypatch.setattr(jeli_service, "generate_narrative", _fake_generate_narrative_fails)
    monkeypatch.setattr(mrs, "send_email", lambda *a, **k: None)
    row = mrs.start_new_report(conn, _USER, "2026-07", "manual")

    updated = await mrs._run_generation(conn, row, _USER, cookie=None)

    assert updated["status"] == "failed"
    assert "empty response" in updated["error_message"]


@pytest.mark.asyncio
async def test_run_generation_failure_with_blank_str_exception_still_sets_nonblank_error(
    monkeypatch, conn
):
    """foroba#281: httpx.ReadTimeout.__str__() is frequently '' — the failed-report
    card must never show a blank explanation."""
    monkeypatch.setattr(jeli_service, "gather_context", _fake_gather_context)
    monkeypatch.setattr(jeli_service, "generate_narrative", _fake_generate_narrative_blank_error)
    monkeypatch.setattr(mrs, "send_email", lambda *a, **k: None)
    row = mrs.start_new_report(conn, _USER, "2026-07", "manual")

    updated = await mrs._run_generation(conn, row, _USER, cookie=None)

    assert updated["status"] == "failed"
    assert updated["error_message"] == "_BlankStrException"


@pytest.mark.asyncio
async def test_run_generation_retry_updates_same_row_without_consuming_quota(monkeypatch, conn):
    monkeypatch.setattr(jeli_service, "gather_context", _fake_gather_context)
    monkeypatch.setattr(jeli_service, "generate_narrative", _fake_generate_narrative_fails)
    monkeypatch.setattr(mrs, "send_email", lambda *a, **k: None)
    row = mrs.start_new_report(conn, _USER, "2026-07", "manual")
    row = await mrs._run_generation(conn, row, _USER, cookie=None)
    assert row["status"] == "failed"
    count_before = db.count_monthly_reports_this_month(
        conn, user_id=_USER["id"], year_month="2026-07"
    )

    retried_row = mrs.start_retry(conn, _USER, row["id"])
    monkeypatch.setattr(jeli_service, "generate_narrative", _fake_generate_narrative)
    retried = await mrs._run_generation(conn, retried_row, _USER, cookie=None)

    assert retried["id"] == row["id"]
    assert retried["status"] == "success"
    assert retried["attempt_count"] == 2
    count_after = db.count_monthly_reports_this_month(
        conn, user_id=_USER["id"], year_month="2026-07"
    )
    assert count_after == count_before


def test_run_generation_in_background_fetches_own_conn_and_runs(monkeypatch, conn):
    """run_generation_in_background wraps asyncio.run() and is only ever invoked by
    FastAPI's BackgroundTasks on its own worker thread (no event loop already
    running there) — same pattern as report_scheduler.py's generate_all_monthly_reports.
    Plain sync test (not @pytest.mark.asyncio) to match that real calling context;
    also confirms it fetches its own conn via get_conn() rather than requiring the
    caller's (foroba#170: never reuse the request thread's connection from a
    background thread) — patch get_conn to the test's in-memory conn and confirm
    the row lands in 'success'."""
    monkeypatch.setattr(jeli_service, "gather_context", _fake_gather_context)
    monkeypatch.setattr(jeli_service, "generate_narrative", _fake_generate_narrative)
    monkeypatch.setattr(mrs, "send_email", lambda *a, **k: None)
    monkeypatch.setattr(mrs, "get_conn", lambda: conn)
    row = mrs.start_new_report(conn, _USER, "2026-07", "manual")

    mrs.run_generation_in_background(row["id"], _USER, cookie=None)

    final = db.get_monthly_report(conn, row["id"], user_id=_USER["id"])
    assert final["status"] == "success"
    assert final["narrative_text"] == "Generated narrative text."
