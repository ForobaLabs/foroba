import sqlite3

from db import init_schema, run_migrations


def _tables(conn: sqlite3.Connection) -> set[str]:
    rows = conn.execute(
        "SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%' "
        "AND name != 'alembic_version'"
    )
    return {row[0] for row in rows}


def _columns(conn: sqlite3.Connection, table: str) -> set[str]:
    return {row[1] for row in conn.execute(f"PRAGMA table_info({table})")}


def test_migrations_match_init_schema(tmp_path):
    """The fast in-memory test schema and the real Alembic migration path
    must never diverge — this fails immediately if a future column is added
    to only one of the two."""
    memory_conn = sqlite3.connect(":memory:")
    init_schema(memory_conn)

    file_db = tmp_path / "migrated.db"
    run_migrations(str(file_db))
    file_conn = sqlite3.connect(str(file_db))

    assert _tables(memory_conn) == _tables(file_conn)
    for table in _tables(memory_conn):
        assert _columns(memory_conn, table) == _columns(file_conn, table), table
