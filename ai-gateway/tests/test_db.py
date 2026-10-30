from pathlib import Path

import sqlcipher3.dbapi2 as sqlcipher

import config
import db


def test_init_schema_creates_four_tables():
    conn = db.connect()
    names = {
        r[0] for r in conn.execute("SELECT name FROM sqlite_master WHERE type='table'")
    }
    assert {"ai_consents", "ai_prefs", "byok_keys", "ai_usage"} <= names
    idx = {
        r[0] for r in conn.execute("SELECT name FROM sqlite_master WHERE type='index'")
    }
    assert "ix_ai_usage_user_at" in idx


def test_consents_allow_accept_withdraw_accept_same_version():
    conn = db.connect()
    for action in ("accept", "withdraw", "accept"):
        conn.execute(
            "INSERT INTO ai_consents(user_id, provider, action, version, at, ip) "
            "VALUES (1, 'cloud', ?, '2026-10-30', '2026-10-30T10:00:00Z', NULL)",
            (action,),
        )
    conn.commit()
    assert conn.execute("SELECT COUNT(*) FROM ai_consents").fetchone()[0] == 3


def test_db_file_is_encrypted():
    db.connect().close()
    raw = Path(config.get_settings().db_path).read_bytes()[:16]
    assert raw != b"SQLite format 3\x00"
    # a connection without the key cannot read it
    plain = sqlcipher.connect(config.get_settings().db_path)
    try:
        plain.execute("SELECT count(*) FROM sqlite_master")
        raise AssertionError("opened encrypted DB without key")
    except sqlcipher.DatabaseError:
        pass
