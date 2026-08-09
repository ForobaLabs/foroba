import sqlite3

from db import init_schema


def test_init_schema_creates_refresh_tokens_table():
    conn = sqlite3.connect(":memory:")
    init_schema(conn)
    cols = {row[1] for row in conn.execute("PRAGMA table_info(refresh_tokens)")}
    assert cols == {
        "id",
        "user_id",
        "token_hash",
        "family_id",
        "device_label",
        "created_at",
        "last_used_at",
        "expires_at",
        "revoked_at",
    }


def test_init_schema_is_idempotent_for_refresh_tokens():
    conn = sqlite3.connect(":memory:")
    init_schema(conn)
    init_schema(conn)  # must not raise
    assert conn.execute("SELECT COUNT(*) FROM refresh_tokens").fetchone()[0] == 0


def test_token_hash_is_unique():
    conn = sqlite3.connect(":memory:")
    init_schema(conn)
    row = (
        1,
        "hash-a",
        "fam-1",
        "iPhone",
        "2026-08-05T00:00:00Z",
        None,
        "2026-09-04T00:00:00Z",
        None,
    )
    sql = (
        "INSERT INTO refresh_tokens "
        "(user_id, token_hash, family_id, device_label,"
        " created_at, last_used_at, expires_at, revoked_at) "
        "VALUES (?, ?, ?, ?, ?, ?, ?, ?)"
    )
    conn.execute(sql, row)
    try:
        conn.execute(sql, row)
        raise AssertionError("expected a UNIQUE constraint violation")
    except sqlite3.IntegrityError:
        pass
