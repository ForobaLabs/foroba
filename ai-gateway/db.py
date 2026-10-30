"""SQLCipher store: consents, prefs, BYOK vault, usage ledger."""

from pathlib import Path

import sqlcipher3.dbapi2 as sqlcipher

from config import get_settings

SCHEMA = """
CREATE TABLE IF NOT EXISTS ai_consents(
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  user_id INTEGER NOT NULL,
  provider TEXT NOT NULL,
  action TEXT NOT NULL CHECK(action IN ('accept','withdraw')),
  version TEXT NOT NULL,
  at TEXT NOT NULL,
  ip TEXT
);
CREATE INDEX IF NOT EXISTS ix_ai_consents_user ON ai_consents(user_id, provider, id);
CREATE TABLE IF NOT EXISTS ai_prefs(
  user_id INTEGER NOT NULL,
  app TEXT NOT NULL,
  feature TEXT NOT NULL,
  provider TEXT NOT NULL CHECK(provider IN ('local','cloud','byok')),
  byok_provider TEXT,
  updated_at TEXT NOT NULL,
  PRIMARY KEY(user_id, app, feature)
);
CREATE TABLE IF NOT EXISTS byok_keys(
  user_id INTEGER NOT NULL,
  provider TEXT NOT NULL,
  secret_enc BLOB NOT NULL,
  account_id_enc BLOB,
  last4 TEXT NOT NULL,
  model TEXT,
  status TEXT NOT NULL,
  created_at TEXT NOT NULL,
  PRIMARY KEY(user_id, provider)
);
CREATE TABLE IF NOT EXISTS ai_usage(
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  user_id INTEGER NOT NULL,
  tier TEXT,
  app TEXT,
  feature TEXT,
  task TEXT,
  provider TEXT,
  model TEXT,
  neurons INTEGER NOT NULL DEFAULT 0,
  latency_ms INTEGER,
  outcome TEXT,
  at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS ix_ai_usage_user_at ON ai_usage(user_id, at);
"""


def init_schema(conn) -> None:
    conn.executescript(SCHEMA)
    conn.commit()


def connect():
    s = get_settings()
    Path(s.db_path).parent.mkdir(parents=True, exist_ok=True)
    conn = sqlcipher.connect(s.db_path, check_same_thread=False, timeout=10)
    escaped = s.db_encryption_key.replace("'", "''")
    conn.execute(f"PRAGMA key = '{escaped}'")
    conn.row_factory = sqlcipher.Row
    conn.execute("PRAGMA journal_mode = WAL")
    conn.execute("PRAGMA busy_timeout = 10000")
    init_schema(conn)
    return conn


def get_conn():
    """FastAPI dependency: one connection per request."""
    conn = connect()
    try:
        yield conn
    finally:
        conn.close()
