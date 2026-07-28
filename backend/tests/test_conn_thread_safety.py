"""Regression tests for foroba#170: concurrent authenticated requests
intermittently returning 401/500 because `auth/conn.py::get_conn()` shared
one sqlite3.Connection across threadpool worker threads (or, in an
interim fix, raced on Alembic's shared migration state when several
threads created their first connection at the same time).
"""
import concurrent.futures
import importlib
import threading

import pytest


@pytest.fixture
def conn_module(tmp_path, monkeypatch):
    """Reload auth.conn against an isolated, real (file-backed) db path so
    each test starts with fresh thread-local/lock state."""
    db_path = str(tmp_path / "test.db")
    import config
    monkeypatch.setattr(config.settings, "auth_db_path", db_path, raising=False)

    import auth.conn as conn_mod
    importlib.reload(conn_mod)
    yield conn_mod
    importlib.reload(conn_mod)


def test_get_conn_gives_each_thread_its_own_connection(conn_module):
    ids: dict[int, int] = {}

    def worker():
        conn = conn_module.get_conn()
        ids[threading.get_ident()] = id(conn)

    threads = [threading.Thread(target=worker) for _ in range(5)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()

    assert len(ids) == 5
    assert len(set(ids.values())) == 5, "each thread must get its own connection object"


def test_get_conn_same_thread_reuses_connection(conn_module):
    first = conn_module.get_conn()
    second = conn_module.get_conn()
    assert first is second


def test_concurrent_first_connection_creation_does_not_race(conn_module):
    """Many threads creating their connection for the very first time at
    once must not crash (this is what reproduced the Alembic
    `KeyError: 'script'` race before `_connect_lock` was added)."""
    errors: list[BaseException] = []

    def worker():
        try:
            conn = conn_module.get_conn()
            conn.execute("SELECT 1").fetchone()
        except BaseException as exc:
            errors.append(exc)

    with concurrent.futures.ThreadPoolExecutor(max_workers=16) as ex:
        list(ex.map(lambda _: worker(), range(16)))

    assert not errors, f"concurrent first-connection creation raised: {errors}"
