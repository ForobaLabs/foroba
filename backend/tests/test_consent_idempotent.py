"""AI-4-F4 — consent accept is idempotent per (user, document, version)."""
import sqlite3

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from auth import repository as repo
from auth.router import get_conn, router
from db import init_schema
from rate_limit import limiter
from settings_store import init_settings

_REG = {
    "email": "idem@y.com",
    "email_confirm": "idem@y.com",
    "name": "Idem",
    "password": "password123",
    "password_confirm": "password123",
    "tos_accepted": True,
}


@pytest.fixture(autouse=True)
def _reset_limiter():
    limiter.reset()
    yield
    limiter.reset()


@pytest.fixture
def ctx():
    conn = sqlite3.connect(":memory:", check_same_thread=False)
    conn.row_factory = sqlite3.Row
    init_schema(conn)
    init_settings(conn)
    app = FastAPI()
    app.dependency_overrides[get_conn] = lambda: conn
    app.include_router(router)
    client = TestClient(app)
    assert client.post("/auth/register", json=_REG).status_code == 201
    uid = conn.execute("SELECT id FROM users WHERE email = ?", (_REG["email"],)).fetchone()[0]
    return client, conn, uid


def _count(conn, uid, doc):
    return conn.execute(
        "SELECT COUNT(*) FROM consents WHERE user_id = ? AND document_type = ?", (uid, doc)
    ).fetchone()[0]


def test_accept_twice_stores_one_row(ctx):
    client, conn, uid = ctx
    before = _count(conn, uid, "terms_of_service")  # registration already recorded one
    for _ in range(2):
        r = client.post("/auth/consents/accept", json={"documents": ["terms_of_service"]})
        assert r.status_code == 204
    assert _count(conn, uid, "terms_of_service") == before == 1


def test_duplicate_docs_in_one_request(ctx):
    client, conn, uid = ctx
    r = client.post(
        "/auth/consents/accept", json={"documents": ["privacy_policy", "privacy_policy"]}
    )
    assert r.status_code == 204
    assert _count(conn, uid, "privacy_policy") == 1


def test_new_version_still_appends(ctx, monkeypatch):
    client, conn, uid = ctx
    monkeypatch.setattr("auth.router.PRIVACY_VERSION", "2999-01-01")
    assert client.post(
        "/auth/consents/accept", json={"documents": ["privacy_policy"]}
    ).status_code == 204
    assert _count(conn, uid, "privacy_policy") == 2
    assert client.get("/auth/consents/status").json()["privacy_policy"] is True


def test_latest_orders_by_id_not_timestamp(ctx):
    _, conn, uid = ctx
    # Same-second acceptances: the later insert (higher id) must win.
    conn.execute("DELETE FROM consents WHERE user_id = ?", (uid,))
    for ver in ("v1", "v2"):
        conn.execute(
            "INSERT INTO consents (user_id, document_type, document_version, accepted_at) "
            "VALUES (?, 'terms_of_service', ?, '2026-01-01 00:00:00')",
            (uid, ver),
        )
    conn.commit()
    assert repo.latest_consent_versions(conn, uid)["terms_of_service"] == "v2"


def test_unique_index_blocks_raw_duplicate(ctx):
    _, conn, uid = ctx
    ver = conn.execute(
        "SELECT document_version FROM consents WHERE user_id = ? LIMIT 1", (uid,)
    ).fetchone()[0]
    doc = conn.execute(
        "SELECT document_type FROM consents WHERE user_id = ? LIMIT 1", (uid,)
    ).fetchone()[0]
    with pytest.raises(sqlite3.IntegrityError):
        conn.execute(
            "INSERT INTO consents (user_id, document_type, document_version) VALUES (?, ?, ?)",
            (uid, doc, ver),
        )


def test_init_schema_dedupes_legacy_duplicates_keeping_earliest():
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    # A pre-fix database: consents table without the unique index, holding duplicates.
    from db import SCHEMA

    conn.executescript(SCHEMA)
    conn.execute(
        "INSERT INTO users (id, email, name, password_hash) VALUES (1, 'a@b.c', 'A', 'x')"
    )
    for ts in ("2026-01-01 00:00:00", "2026-02-02 00:00:00", "2026-03-03 00:00:00"):
        conn.execute(
            "INSERT INTO consents (user_id, document_type, document_version, accepted_at) "
            "VALUES (1, 'terms_of_service', 'v1', ?)",
            (ts,),
        )
    conn.commit()
    init_schema(conn)
    rows = conn.execute("SELECT accepted_at FROM consents").fetchall()
    assert [r[0] for r in rows] == ["2026-01-01 00:00:00"]
    init_schema(conn)  # idempotent
