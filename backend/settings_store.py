"""Runtime settings store — lightweight toggle table in the auth SQLite DB."""
from __future__ import annotations

import sqlite3
from datetime import UTC, datetime

_SCHEMA = (
    "CREATE TABLE IF NOT EXISTS runtime_settings "
    "(key TEXT PRIMARY KEY, value TEXT NOT NULL, updated_at TEXT NOT NULL)"
)

DEFAULT_SETTINGS: dict[str, str] = {
    "premium_gating_enabled": "false",
    "onboarding_mifid_enabled": "false",
    "lab_service_enabled": "true",
    # Balance threshold (cents) below which the "low balance" notification
    # fires (foroba#158, notification_service.py). Not a toggle but reuses
    # this same key/value store rather than adding a new table.
    "low_balance_threshold_cents": "10000",
}


def init_settings(conn: sqlite3.Connection) -> None:
    """Create table and seed defaults if missing. Idempotent."""
    conn.execute(_SCHEMA)
    conn.commit()
    for key, value in DEFAULT_SETTINGS.items():
        conn.execute(
            "INSERT OR IGNORE INTO runtime_settings (key, value, updated_at) "
            "VALUES (?, ?, ?)",
            (key, value, _now()),
        )
    conn.commit()


def get_all(conn: sqlite3.Connection) -> dict[str, str]:
    rows = conn.execute("SELECT key, value FROM runtime_settings").fetchall()
    return {r["key"]: r["value"] for r in rows}


def set_value(conn: sqlite3.Connection, key: str, value: str) -> None:
    if key not in DEFAULT_SETTINGS:
        raise ValueError(f"Unknown setting key: {key!r}")
    conn.execute(
        "UPDATE runtime_settings SET value = ?, updated_at = ? WHERE key = ?",
        (value, _now(), key),
    )
    conn.commit()


def _now() -> str:
    return datetime.now(UTC).isoformat()
