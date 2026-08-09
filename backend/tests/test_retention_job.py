"""CL-2.3 — retention job: automated per-category deletion (foroba#240)."""
import sqlite3

import pytest

from db import init_schema
from retention_job import purge_expired


@pytest.fixture
def tmp_conn():
    conn = sqlite3.connect(":memory:", check_same_thread=False)
    conn.row_factory = sqlite3.Row
    init_schema(conn)
    return conn


def test_purges_stale_webauthn_challenges(tmp_conn):
    tmp_conn.execute(
        "INSERT INTO webauthn_challenges (user_id, challenge, purpose, created_at) "
        "VALUES (1, 'x', 'registration', datetime('now','-2 days'))"
    )
    tmp_conn.commit()
    purge_expired(tmp_conn, now_days=1)
    n = tmp_conn.execute("SELECT count(*) FROM webauthn_challenges").fetchone()[0]
    assert n == 0


def test_keeps_fresh_webauthn_challenges(tmp_conn):
    tmp_conn.execute(
        "INSERT INTO webauthn_challenges (user_id, challenge, purpose, created_at) "
        "VALUES (1, 'y', 'registration', datetime('now'))"
    )
    tmp_conn.commit()
    purge_expired(tmp_conn, now_days=1)
    assert tmp_conn.execute("SELECT count(*) FROM webauthn_challenges").fetchone()[0] == 1


def test_purges_fulfilled_dsar_requests(tmp_conn):
    tmp_conn.execute(
        "INSERT INTO dsar_requests (user_id, kind, status, resolved_at) "
        "VALUES (1, 'access', 'fulfilled', datetime('now','-400 days'))"
    )
    tmp_conn.commit()
    purge_expired(tmp_conn, now_days=365)
    assert tmp_conn.execute("SELECT count(*) FROM dsar_requests").fetchone()[0] == 0


def test_keeps_open_dsar_requests(tmp_conn):
    tmp_conn.execute(
        "INSERT INTO dsar_requests (user_id, kind, status) VALUES (1, 'access', 'open')"
    )
    tmp_conn.commit()
    purge_expired(tmp_conn, now_days=1)
    assert tmp_conn.execute("SELECT count(*) FROM dsar_requests").fetchone()[0] == 1
