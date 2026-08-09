"""CL-2.4 — security event log + alerting (foroba#241)."""
import sqlite3

import pytest

from db import init_schema
from security_log import log_event, recent_events


@pytest.fixture
def tmp_conn():
    conn = sqlite3.connect(":memory:", check_same_thread=False)
    conn.row_factory = sqlite3.Row
    init_schema(conn)
    return conn


def test_log_and_read_back(tmp_conn):
    log_event(tmp_conn, user_id=1, event="login_failed", detail="bad password", ip="1.2.3.4")
    rows = recent_events(tmp_conn, limit=10)
    assert rows[0]["event"] == "login_failed"
    assert rows[0]["ip"] == "1.2.3.4"
    assert rows[0]["detail"] == "bad password"


def test_alert_on_repeated_failures(tmp_conn, monkeypatch):
    calls: list[str] = []
    monkeypatch.setattr("security_log._alert", lambda msg: calls.append(msg))
    for _ in range(5):
        log_event(tmp_conn, user_id=1, event="login_failed", detail="x", ip="9.9.9.9")
    assert calls, "expected an alert after repeated login failures"
    assert "login_failed" in calls[0]


def test_no_alert_below_threshold(tmp_conn, monkeypatch):
    calls: list[str] = []
    monkeypatch.setattr("security_log._alert", lambda msg: calls.append(msg))
    for _ in range(4):
        log_event(tmp_conn, user_id=1, event="login_failed", detail="x", ip="8.8.8.8")
    assert not calls


def test_non_alert_event_never_alerts(tmp_conn, monkeypatch):
    calls: list[str] = []
    monkeypatch.setattr("security_log._alert", lambda msg: calls.append(msg))
    for _ in range(10):
        log_event(tmp_conn, user_id=1, event="login_success", detail="ok", ip="1.1.1.1")
    assert not calls
