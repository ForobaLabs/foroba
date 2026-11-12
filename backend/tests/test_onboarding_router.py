import sqlite3

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from auth.dependencies import get_current_user
from auth.router import get_conn
from db import init_schema, seed_mock_users
from onboarding.router import router


@pytest.fixture
def app_conn():
    conn = sqlite3.connect(":memory:", check_same_thread=False)
    conn.row_factory = sqlite3.Row
    init_schema(conn)
    seed_mock_users(conn)
    app = FastAPI()
    app.dependency_overrides[get_conn] = lambda: conn
    app.dependency_overrides[get_current_user] = lambda: dict(
        conn.execute("SELECT * FROM users WHERE email='demo@foroba.app'").fetchone()
    )
    app.include_router(router)
    return TestClient(app), conn


def test_get_questionnaire(app_conn):
    c, _ = app_conn
    r = c.get("/onboarding/mifid")
    assert r.status_code == 200
    assert "questions" in r.json()


def test_submit_sets_and_locks_audience(app_conn):
    c, conn = app_conn
    answers = {"experience": 3, "instruments": 3, "frequency": 2, "knowledge": 2, "risk": 2}
    r = c.post("/onboarding/mifid", json={"answers": answers})
    assert r.status_code == 200
    assert r.json()["audience"] == "expert"
    row = conn.execute(
        "SELECT audience, audience_locked FROM users WHERE email='demo@foroba.app'"
    ).fetchone()
    assert row["audience"] == "expert" and row["audience_locked"] == 1


def test_manual_toggle(app_conn):
    c, conn = app_conn
    r = c.patch("/auth/audience", json={"audience": "expert"})
    assert r.status_code == 200
    row = conn.execute("SELECT audience FROM users WHERE email='demo@foroba.app'").fetchone()
    assert row["audience"] == "expert"


_FULL = {"experience": 3, "instruments": 3, "frequency": 2, "knowledge": 2, "risk": 2}


@pytest.mark.parametrize(
    "answers",
    [
        {},  # nothing answered
        {"experience": 3},  # partial
        {**_FULL, "experience": 99},  # out of range
        {**_FULL, "experience": -1},  # negative index
    ],
)
def test_submit_rejects_incomplete_or_out_of_range_answers(app_conn, answers):
    c, conn = app_conn
    before = conn.execute(
        "SELECT audience, audience_locked FROM users WHERE email='demo@foroba.app'"
    ).fetchone()
    r = c.post("/onboarding/mifid", json={"answers": answers})
    assert r.status_code == 422
    after = conn.execute(
        "SELECT audience, audience_locked FROM users WHERE email='demo@foroba.app'"
    ).fetchone()
    assert tuple(after) == tuple(before)  # nothing locked by a rejected submission
