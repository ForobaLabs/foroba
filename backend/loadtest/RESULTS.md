# TI-B item 7 — Load test results (foroba#156)

**Date:** 2026-07-15. **Goal:** measure where SQLite/the Foroba backend degrades under
household-scale concurrent usage (not internet-scale). Tool: Locust (`loadtest/locustfile.py`).

## Real bug found + fixed
`db.py::connect()` opened the shared singleton SQLite connection (`auth/conn.py`, used across
all FastAPI threadpool workers) in default rollback-journal mode with no explicit
`busy_timeout`. Under concurrent writes (login attempt counters, registrations) this could
produce `database is locked` `OperationalError`s (observed as unhandled 500s) once write
contention rose. **Fix:** `PRAGMA journal_mode = WAL` + `PRAGMA busy_timeout = 10000` (10s) on
the shared connection, plus `sqlite3.connect(..., timeout=10)`. WAL allows concurrent readers
while a single writer holds the lock; the busy_timeout makes writers queue instead of failing
immediately on contention. Verified live: `foroba_identity.db-wal`/`-shm` present,
`PRAGMA journal_mode` reports `wal`.

## Test run
15 simulated users (3 Anonymous, 10 Authenticated, 2 Register — locust weight-proportional),
spawn rate 1/s, duration 90s, against `http://localhost:8002` (uvicorn, no --reload).

| Endpoint | Requests | Failures | Median | p99 | Max |
|---|---|---|---|---|---|
| GET /auth/me | 145 | 0 | 4ms | 60ms | 85ms |
| GET /auth/household | 45 | 0 | 4ms | 49ms | 49ms |
| GET /markets/snapshot | 107 | 0 | 29ms | 62ms | 97ms |
| GET /markets/overview | 109 | 0 | 29ms | 53ms | 122ms |
| POST /auth/login | 23 | 9 (429) | 150ms | 180ms | 181ms |
| POST /auth/register | 50 | 40 (429) | 6ms | 280ms | 281ms |
| GET /health | 109 | 54 (429) | 4ms | 33ms | 33ms |

**Zero 500s, zero timeouts/hangs across 588 requests.** All 103 failures are `429 Too Many
Requests` from the item-6 per-IP slowapi rate limiters (`/auth/login` 10/min, `/auth/register`
5/min, `/health` 1/sec) — these are `key_func=get_remote_address`, so every simulated user
launched from the same test machine shares one bucket. This is correct, intended behavior
(anti-brute-force + anti-hammering), not a load-test failure; it just means a single-machine
Locust run cannot exercise login/register concurrency beyond the per-IP quota. Real households
behind a shared NAT IP would see the same throttling on login bursts, which is an acceptable
trade-off at this scale.

## Conclusion
At household scale (~15 concurrent users, ~6.6 req/s sustained), SQLite (WAL mode) + the
Foroba FastAPI backend show no degradation: all read endpoints stayed under 100ms even at p99,
and no lock contention errors occurred post-fix. The practical ceiling for this architecture is
the intentional per-IP rate limiters, not SQLite itself. No further scaling work is needed for
the "family/household" scope this ticket targets.
