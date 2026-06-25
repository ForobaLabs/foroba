"""Parametrised CRUD over the users table. No SQL string interpolation."""
from __future__ import annotations

import sqlite3


def _row_to_dict(row: sqlite3.Row | None) -> dict | None:
    return dict(row) if row is not None else None


def create_user(conn: sqlite3.Connection, *, email: str, name: str,
                password_hash: str, tier: str = "free",
                audience: str = "base") -> dict:
    cur = conn.execute(
        "INSERT INTO users (email, name, password_hash, tier, audience) "
        "VALUES (?, ?, ?, ?, ?)",
        (email, name, password_hash, tier, audience),
    )
    conn.commit()
    return get_user_by_id(conn, cur.lastrowid)


def get_user_by_email(conn: sqlite3.Connection, email: str) -> dict | None:
    row = conn.execute("SELECT * FROM users WHERE email = ?", (email,)).fetchone()
    return _row_to_dict(row)


def get_user_by_id(conn: sqlite3.Connection, user_id: int) -> dict | None:
    row = conn.execute("SELECT * FROM users WHERE id = ?", (user_id,)).fetchone()
    return _row_to_dict(row)


def set_audience(conn: sqlite3.Connection, user_id: int, audience: str,
                 *, locked: bool) -> None:
    conn.execute(
        "UPDATE users SET audience = ?, audience_locked = ? WHERE id = ?",
        (audience, 1 if locked else 0, user_id),
    )
    conn.commit()


def list_all_users(conn: sqlite3.Connection) -> list[dict]:
    rows = conn.execute("SELECT * FROM users ORDER BY id").fetchall()
    return [dict(r) for r in rows]
