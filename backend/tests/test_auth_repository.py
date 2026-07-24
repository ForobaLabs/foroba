import sqlite3

import pytest

from auth import repository as repo
from db import init_schema


@pytest.fixture
def conn():
    connection = sqlite3.connect(":memory:", check_same_thread=False)
    connection.row_factory = sqlite3.Row
    init_schema(connection)
    return connection


def test_set_show_debts_persists_value(conn):
    repo.create_user(
        conn, email="debts-test@example.com", name="Debts Test",
        password_hash="x", tier="free", audience="base",
    )
    user = repo.get_user_by_email(conn, "debts-test@example.com")
    assert bool(user["show_debts"]) is False

    repo.set_show_debts(conn, user["id"], True)
    updated = repo.get_user_by_email(conn, "debts-test@example.com")
    assert bool(updated["show_debts"]) is True
