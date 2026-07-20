"""CRUD tests for monthly_reports (foroba#159, TI-D item 2)."""
from __future__ import annotations

import sqlite3

import pytest

import db


@pytest.fixture
def conn():
    c = sqlite3.connect(":memory:")
    c.row_factory = sqlite3.Row
    db.init_schema(c)
    return c


def test_create_and_get_report(conn):
    row = db.create_monthly_report(conn, user_id=1, year_month="2026-07", trigger="manual")
    assert row["status"] == "generating"
    assert row["year_month"] == "2026-07"
    fetched = db.get_monthly_report(conn, row["id"], user_id=1)
    assert fetched is not None
    assert fetched["id"] == row["id"]


def test_get_report_denies_other_user(conn):
    row = db.create_monthly_report(conn, user_id=1, year_month="2026-07", trigger="manual")
    assert db.get_monthly_report(conn, row["id"], user_id=2) is None


def test_list_reports_ordered_newest_first(conn):
    db.create_monthly_report(conn, user_id=1, year_month="2026-06", trigger="manual")
    db.create_monthly_report(conn, user_id=1, year_month="2026-07", trigger="manual")
    rows = db.list_monthly_reports(conn, user_id=1)
    assert [r["year_month"] for r in rows] == ["2026-07", "2026-06"]


def test_list_reports_filtered_by_year_month(conn):
    db.create_monthly_report(conn, user_id=1, year_month="2026-06", trigger="manual")
    db.create_monthly_report(conn, user_id=1, year_month="2026-07", trigger="manual")
    rows = db.list_monthly_reports(conn, user_id=1, year_month="2026-06")
    assert len(rows) == 1
    assert rows[0]["year_month"] == "2026-06"


def test_count_reports_this_month(conn):
    db.create_monthly_report(conn, user_id=1, year_month="2026-07", trigger="manual")
    db.create_monthly_report(conn, user_id=1, year_month="2026-07", trigger="manual")
    db.create_monthly_report(conn, user_id=1, year_month="2026-06", trigger="manual")
    assert db.count_monthly_reports_this_month(conn, user_id=1, year_month="2026-07") == 2


def test_update_report_result_success(conn):
    row = db.create_monthly_report(conn, user_id=1, year_month="2026-07", trigger="manual")
    updated = db.update_monthly_report_result(
        conn, row["id"], status="success", narrative_text="Summary text",
        context_snapshot_json='{"a": 1}', error_message=None, attempt_count=1,
    )
    assert updated["status"] == "success"
    assert updated["narrative_text"] == "Summary text"
    assert updated["attempt_count"] == 1


def test_update_report_result_failure(conn):
    row = db.create_monthly_report(conn, user_id=1, year_month="2026-07", trigger="manual")
    updated = db.update_monthly_report_result(
        conn, row["id"], status="failed", narrative_text=None,
        context_snapshot_json=None, error_message="Ollama timeout", attempt_count=4,
    )
    assert updated["status"] == "failed"
    assert updated["error_message"] == "Ollama timeout"
    assert updated["attempt_count"] == 4
