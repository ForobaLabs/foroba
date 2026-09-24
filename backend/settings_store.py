"""Runtime settings store — lightweight toggle table in the auth SQLite DB."""

from __future__ import annotations

import sqlite3
from datetime import UTC, datetime

_SCHEMA = (
    "CREATE TABLE IF NOT EXISTS runtime_settings "
    "(key TEXT PRIMARY KEY, value TEXT NOT NULL, updated_at TEXT NOT NULL)"
)

DEFAULT_SETTINGS: dict[str, str] = {
    # Plan V (pazuru#152 / tsumi#230): the paywall must be enforced by default.
    # Previously "false", which silently shipped every premium feature suite-wide
    # unlocked for free-tier accounts and went unnoticed for weeks.
    "premium_gating_enabled": "true",
    "onboarding_mifid_enabled": "false",
    "lab_service_enabled": "true",
    # Balance threshold (cents) below which the "low balance" notification
    # fires (foroba#158, notification_service.py). Not a toggle but reuses
    # this same key/value store rather than adding a new table.
    "low_balance_threshold_cents": "10000",
    # GL-10.1 (foroba#185): when true, /auth/register requires a valid,
    # unexpired, unrevoked invite code (see invite_codes table). Off by
    # default so self-host deployments keep open registration unchanged.
    "require_invite_code": "false",
}


def init_settings(conn: sqlite3.Connection) -> None:
    """Create table and seed defaults if missing. Idempotent."""
    conn.execute(_SCHEMA)
    conn.commit()
    for key, value in DEFAULT_SETTINGS.items():
        conn.execute(
            "INSERT OR IGNORE INTO runtime_settings (key, value, updated_at) VALUES (?, ?, ?)",
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


# Settings whose live value must not silently drift from this expected value
# without the business explicitly re-deciding it (Plan V, pazuru#152 / tsumi#230):
# premium_gating_enabled sat at "false" in production for weeks because nothing
# monitored it. Extend this dict if another toggle needs the same guarantee.
EXPECTED_SETTINGS: dict[str, str] = {
    "premium_gating_enabled": "true",
}


def check_drift(conn: sqlite3.Connection) -> dict[str, str]:
    """Return {key: actual_value} for each EXPECTED_SETTINGS entry whose live
    value doesn't match what's expected. Empty dict means no drift."""
    current = get_all(conn)
    return {
        key: current.get(key, "<missing>")
        for key, expected in EXPECTED_SETTINGS.items()
        if current.get(key) != expected
    }
