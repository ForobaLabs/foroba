"""Shared singleton connection for the identity DB."""
from __future__ import annotations

import sqlite3

from config import settings
from db import connect

_conn: sqlite3.Connection | None = None


def get_conn() -> sqlite3.Connection:
    global _conn
    if _conn is None:
        _conn = connect(settings.auth_db_path)
    return _conn
