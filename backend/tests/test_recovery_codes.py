import sqlite3

from db import init_schema
from recovery_codes import generate_and_store, remaining_count, verify_and_consume


def _conn_with_user() -> tuple[sqlite3.Connection, int]:
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    init_schema(conn)
    conn.execute(
        "INSERT INTO users (email, password_hash, name) VALUES ('r@example.com', 'h', 'R')"
    )
    conn.commit()
    user_id = conn.execute("SELECT id FROM users WHERE email = 'r@example.com'").fetchone()["id"]
    return conn, user_id


def test_generate_and_store_returns_ten_unique_codes():
    conn, user_id = _conn_with_user()
    codes = generate_and_store(conn, user_id)
    assert len(codes) == 10
    assert len(set(codes)) == 10


def test_verify_and_consume_accepts_valid_code_once():
    conn, user_id = _conn_with_user()
    codes = generate_and_store(conn, user_id)
    assert verify_and_consume(conn, user_id, codes[0]) is True
    assert verify_and_consume(conn, user_id, codes[0]) is False  # single-use


def test_verify_and_consume_rejects_unknown_code():
    conn, user_id = _conn_with_user()
    generate_and_store(conn, user_id)
    assert verify_and_consume(conn, user_id, "NOTACODE1") is False


def test_remaining_count_decreases_after_use():
    conn, user_id = _conn_with_user()
    codes = generate_and_store(conn, user_id)
    assert remaining_count(conn, user_id) == 10
    verify_and_consume(conn, user_id, codes[0])
    assert remaining_count(conn, user_id) == 9


def test_regenerate_invalidates_old_set():
    conn, user_id = _conn_with_user()
    old_codes = generate_and_store(conn, user_id)
    generate_and_store(conn, user_id)
    assert verify_and_consume(conn, user_id, old_codes[0]) is False
