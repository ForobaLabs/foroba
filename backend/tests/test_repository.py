import sqlite3

import pytest

from auth import repository as repo
from db import init_schema


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




def test_set_audience_locks(conn):
    u = repo.create_user(conn, email="m@n.com", name="M", password_hash="h")
    repo.set_audience(conn, u["id"], "expert", locked=True)
    updated = repo.get_user_by_id(conn, u["id"])
    assert updated["audience"] == "expert"
    assert updated["audience_locked"] == 1


from db import seed_mock_users


def test_seed_mock_users_idempotent(conn):
    created = seed_mock_users(conn)
    assert len(created) == 4
    # second call adds nothing
    again = seed_mock_users(conn)
    assert again == []
    rows = conn.execute("SELECT email FROM users ORDER BY email").fetchall()
    emails = [r["email"] for r in rows]
    assert "demo@foroba.app" in emails


def test_totp_lifecycle(conn):
    from auth import repository as repo
    u = repo.create_user(conn, email="t@f.com", name="T", password_hash="h")
    repo.set_totp_secret(conn, u["id"], "SECRET234567")
    assert repo.get_user_by_id(conn, u["id"])["totp_secret"] == "SECRET234567"
    assert repo.get_user_by_id(conn, u["id"])["totp_enabled"] == 0
    repo.enable_totp(conn, u["id"])
    assert repo.get_user_by_id(conn, u["id"])["totp_enabled"] == 1
    repo.disable_totp(conn, u["id"])
    row = repo.get_user_by_id(conn, u["id"])
    assert row["totp_enabled"] == 0 and row["totp_secret"] is None
