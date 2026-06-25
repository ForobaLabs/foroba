"""SQLite identity store for the Foroba backend (suite identity authority)."""
from __future__ import annotations

import sqlite3
from pathlib import Path

SCHEMA = """
CREATE TABLE IF NOT EXISTS users (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    email TEXT NOT NULL UNIQUE,
    name TEXT NOT NULL,
    password_hash TEXT NOT NULL,
    tier TEXT NOT NULL DEFAULT 'free',
    audience TEXT NOT NULL DEFAULT 'base',
    audience_locked INTEGER NOT NULL DEFAULT 0,
    totp_secret TEXT,
    totp_enabled INTEGER NOT NULL DEFAULT 0,
    created_at TEXT NOT NULL DEFAULT (datetime('now'))
);
"""


def init_schema(conn: sqlite3.Connection) -> None:
    conn.executescript(SCHEMA)
    conn.commit()


from auth.security import hash_password

# (email, name, plaintext password, tier, audience)
MOCK_USERS = [
    ("demo@foroba.app", "Demo Base", "Demo!2026", "free", "base"),
    ("pro@foroba.app", "Pro Expert", "Pro!2026", "premium", "expert"),
    ("test@foroba.app", "Test User", "Test!2026", "free", "base"),
]


def seed_mock_users(conn: sqlite3.Connection) -> list[str]:
    """Insert mock users that do not already exist. Returns created emails."""
    created: list[str] = []
    for email, name, pw, tier, audience in MOCK_USERS:
        exists = conn.execute(
            "SELECT 1 FROM users WHERE email = ?", (email,)
        ).fetchone()
        if exists:
            continue
        conn.execute(
            "INSERT INTO users (email, name, password_hash, tier, audience) "
            "VALUES (?, ?, ?, ?, ?)",
            (email, name, hash_password(pw), tier, audience),
        )
        created.append(email)
    conn.commit()
    return created


def connect(db_path: str) -> sqlite3.Connection:
    Path(db_path).parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(db_path, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    init_schema(conn)
    return conn
