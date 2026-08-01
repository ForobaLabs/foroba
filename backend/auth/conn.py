"""Per-thread connection for the identity DB.

Previously this was a single process-wide singleton `sqlite3.Connection`
shared across every request. FastAPI's sync route dependencies (the vast
majority of this backend's routes, including this one) run on Starlette's
threadpool, so concurrent requests could execute against that one shared
connection object on different OS threads at the same time. Python's
sqlite3 docs are explicit that `check_same_thread=False` only disables the
same-thread safety check — it does not make concurrent use of one
Connection from multiple threads safe; the caller must serialize access
itself. Sharing one connection caused an intermittent bug (foroba#170):
two authenticated requests fired concurrently on the same session could
race and one would get a wrong/empty read (e.g. `get_user_by_id` returning
None -> spurious 401 "Unknown user"), even though a single request always
succeeded.

Fix: give each worker thread its own connection (thread-local), all
pointing at the same DB file. WAL mode + busy_timeout (set in
db.connect()) already make concurrent readers safe and serialize
concurrent writers at the SQLite level, so per-thread connections remove
the shared-object race without needing an app-level lock across the ~36
call sites that depend on `get_conn`.

`db.connect()` runs Alembic migrations (`run_migrations`) on every call
for a real (non-":memory:") db_path. Alembic's `EnvironmentContext`
mutates shared module-level global state while running, which is itself
not safe to invoke from two threads at once — confirmed by reproducing a
`KeyError: 'script'` crash when two brand-new worker threads both created
their first connection concurrently. `_connect_lock` serializes connection
creation (which only happens once per distinct worker thread, not per
request) so `connect()`/`run_migrations()` never runs concurrently, while
each thread still ends up with its own private connection object.
"""

from __future__ import annotations

import sqlite3
import threading

from config import settings
from db import connect

_local = threading.local()
_connect_lock = threading.Lock()


def get_conn() -> sqlite3.Connection:
    conn: sqlite3.Connection | None = getattr(_local, "conn", None)
    if conn is None:
        with _connect_lock:
            conn = connect(settings.auth_db_path)
        _local.conn = conn
    return conn
