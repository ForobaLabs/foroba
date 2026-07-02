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
    is_admin INTEGER NOT NULL DEFAULT 0,
    created_at TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS sandbox_conversations (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id TEXT NOT NULL,
    session_id TEXT NOT NULL,
    role TEXT NOT NULL,
    content TEXT NOT NULL,
    code TEXT,
    artifacts_json TEXT,
    created_at TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS sandbox_user_context (
    user_id TEXT PRIMARY KEY,
    context_text TEXT NOT NULL DEFAULT '',
    updated_at TEXT NOT NULL DEFAULT (datetime('now'))
);
"""


def init_schema(conn: sqlite3.Connection) -> None:
    conn.executescript(SCHEMA)
    conn.commit()
    # Idempotent migration: add is_admin column if it doesn't exist
    try:
        conn.execute("ALTER TABLE users ADD COLUMN is_admin INTEGER NOT NULL DEFAULT 0")
        conn.commit()
    except sqlite3.OperationalError:
        pass  # column already exists


from auth.security import hash_password

# (email, name, plaintext password, tier, audience, is_admin)
MOCK_USERS = [
    ("demo@foroba.app", "Demo Base", "Demo!2026", "free", "base", 0),
    ("pro@foroba.app", "Pro Expert", "Pro!2026", "premium", "expert", 0),
    ("test@foroba.app", "Test User", "Test!2026", "free", "base", 0),
    ("admin@foroba.app", "Foroba Admin", "Admin1234!", "free", "base", 1),
]


def seed_mock_users(conn: sqlite3.Connection) -> list[str]:
    """Insert mock users that do not already exist. Returns created emails."""
    created: list[str] = []
    for email, name, pw, tier, audience, is_admin in MOCK_USERS:
        exists = conn.execute(
            "SELECT 1 FROM users WHERE email = ?", (email,)
        ).fetchone()
        if exists:
            continue
        conn.execute(
            "INSERT INTO users (email, name, password_hash, tier, audience, is_admin) "
            "VALUES (?, ?, ?, ?, ?, ?)",
            (email, name, hash_password(pw), tier, audience, is_admin),
        )
        created.append(email)
    conn.commit()
    return created


def save_sandbox_turn(
    conn: sqlite3.Connection,
    user_id: str,
    session_id: str,
    question: str,
    answer: str,
    code: str | None = None,
    artifacts_json: str | None = None,
) -> None:
    """Persist a user question + assistant answer as two conversation rows."""
    conn.execute(
        "INSERT INTO sandbox_conversations (user_id, session_id, role, content) VALUES (?, ?, 'user', ?)",
        (user_id, session_id, question),
    )
    conn.execute(
        "INSERT INTO sandbox_conversations (user_id, session_id, role, content, code, artifacts_json) "
        "VALUES (?, ?, 'assistant', ?, ?, ?)",
        (user_id, session_id, answer, code, artifacts_json),
    )
    conn.commit()


def get_sandbox_history(
    conn: sqlite3.Connection, user_id: str, session_id: str, limit: int = 20
) -> list[dict]:
    """Return the most recent `limit` conversation rows, in chronological order."""
    rows = conn.execute(
        "SELECT role, content, code FROM sandbox_conversations "
        "WHERE user_id = ? AND session_id = ? ORDER BY created_at DESC, id DESC LIMIT ?",
        (user_id, session_id, limit),
    ).fetchall()
    result = [dict(row) for row in rows]
    result.reverse()
    return result


def get_sandbox_user_context(conn: sqlite3.Connection, user_id: str) -> str:
    row = conn.execute(
        "SELECT context_text FROM sandbox_user_context WHERE user_id = ?", (user_id,)
    ).fetchone()
    return row["context_text"] if row else ""


def update_sandbox_user_context(conn: sqlite3.Connection, user_id: str, context_text: str) -> None:
    conn.execute(
        "INSERT INTO sandbox_user_context (user_id, context_text, updated_at) "
        "VALUES (?, ?, datetime('now')) "
        "ON CONFLICT(user_id) DO UPDATE SET context_text = excluded.context_text, updated_at = excluded.updated_at",
        (user_id, context_text),
    )
    conn.commit()


def connect(db_path: str) -> sqlite3.Connection:
    Path(db_path).parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(db_path, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    init_schema(conn)
    return conn
