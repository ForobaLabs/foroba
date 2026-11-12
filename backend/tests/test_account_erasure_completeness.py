"""Task 2.8: Art. 17 erasure leaves no user-keyed row behind, Art. 20 export leaks no secrets."""

from __future__ import annotations

import db
from auth import repository as repo

ERASED_TABLES = {
    "refresh_tokens": (
        "INSERT INTO refresh_tokens (user_id, token_hash, family_id, created_at, expires_at) "
        "VALUES (?, 'h', 'f', 'now', 'later')"
    ),
    "device_push_tokens": (
        "INSERT INTO device_push_tokens (user_id, token, platform, registered_at) "
        "VALUES (?, 't', 'ios', 'now')"
    ),
    "dsar_requests": "INSERT INTO dsar_requests (user_id, kind) VALUES (?, 'export')",
    "invite_codes": "INSERT INTO invite_codes (code, created_by_user_id) VALUES ('c', ?)",
}
SECURITY_EVENT = (
    "INSERT INTO security_events (user_id, event, detail, ip) VALUES (?, 'login', 'd', '1.2.3.4')"
)


def _user(conn):
    repo.create_user(
        conn, email="gone@test.local", name="G", password_hash="x", tier="free", audience="base"
    )
    return repo.get_user_by_email(conn, "gone@test.local")["id"]


def test_delete_user_leaves_no_user_keyed_row_in_any_table():
    conn = db.connect(":memory:")
    uid = _user(conn)
    for sql in ERASED_TABLES.values():
        conn.execute(sql, (uid,))
    conn.execute(SECURITY_EVENT, (uid,))
    conn.commit()

    repo.delete_user(conn, uid)

    leftovers = {}
    for (table,) in conn.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall():
        for col in (r[1] for r in conn.execute(f"PRAGMA table_info({table})")):
            if col in ("user_id", "created_by_user_id"):
                n = conn.execute(
                    f"SELECT COUNT(*) FROM {table} WHERE {col} = ?", (uid,)
                ).fetchone()[0]
                if n:
                    leftovers[f"{table}.{col}"] = n
    assert leftovers == {}


def test_security_events_are_anonymised_not_kept_with_ip():
    conn = db.connect(":memory:")
    uid = _user(conn)
    conn.execute(SECURITY_EVENT, (uid,))
    conn.commit()
    repo.delete_user(conn, uid)
    left = conn.execute("SELECT COUNT(*) FROM security_events WHERE ip IS NOT NULL").fetchone()[0]
    assert left == 0
