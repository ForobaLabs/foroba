import sqlite3

import pytest

from db import init_schema
from auth import repository as repo


@pytest.fixture
def conn():
    c = sqlite3.connect(":memory:")
    c.row_factory = sqlite3.Row
    init_schema(c)
    yield c
    c.close()


def test_create_and_get_user(conn):
    user = repo.create_user(conn, email="a@b.com", name="Ada", password_hash="h")
    assert user["id"] > 0
    assert user["email"] == "a@b.com"
    assert user["tier"] == "free"
    assert user["audience"] == "base"

    found = repo.get_user_by_email(conn, "a@b.com")
    assert found["id"] == user["id"]


def test_email_unique(conn):
    repo.create_user(conn, email="a@b.com", name="Ada", password_hash="h")
    with pytest.raises(sqlite3.IntegrityError):
        repo.create_user(conn, email="a@b.com", name="Dup", password_hash="h")


def test_get_missing_returns_none(conn):
    assert repo.get_user_by_email(conn, "none@x.com") is None
    assert repo.get_user_by_id(conn, 999) is None


from auth import repository as repo


def test_set_audience_locks(conn):
    u = repo.create_user(conn, email="m@n.com", name="M", password_hash="h")
    repo.set_audience(conn, u["id"], "expert", locked=True)
    updated = repo.get_user_by_id(conn, u["id"])
    assert updated["audience"] == "expert"
    assert updated["audience_locked"] == 1


from db import seed_mock_users


def test_seed_mock_users_idempotent(conn):
    created = seed_mock_users(conn)
    assert len(created) == 3
    # second call adds nothing
    again = seed_mock_users(conn)
    assert again == []
    rows = conn.execute("SELECT email FROM users ORDER BY email").fetchall()
    emails = [r["email"] for r in rows]
    assert "demo@foroba.app" in emails
