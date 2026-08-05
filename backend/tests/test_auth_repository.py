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
        conn,
        email="debts-test@example.com",
        name="Debts Test",
        password_hash="x",
        tier="free",
        audience="base",
    )
    user = repo.get_user_by_email(conn, "debts-test@example.com")
    assert bool(user["show_debts"]) is False

    repo.set_show_debts(conn, user["id"], True)
    updated = repo.get_user_by_email(conn, "debts-test@example.com")
    assert bool(updated["show_debts"]) is True


def test_record_and_get_consents(conn):
    user = repo.create_user(
        conn, email="consent@example.com", name="Consent Test", password_hash="x"
    )
    assert repo.get_consents(conn, user["id"]) == []

    repo.record_consent(
        conn,
        user_id=user["id"],
        document_type="terms_of_service",
        document_version="2026-07-31",
        ip_address="127.0.0.1",
    )
    repo.record_consent(
        conn,
        user_id=user["id"],
        document_type="privacy_policy",
        document_version="2026-07-31",
        ip_address="127.0.0.1",
    )

    consents = repo.get_consents(conn, user["id"])
    assert len(consents) == 2
    types = {c["document_type"] for c in consents}
    assert types == {"terms_of_service", "privacy_policy"}
    assert all(c["document_version"] == "2026-07-31" for c in consents)


def test_create_user_splits_name_into_first_last(conn):
    repo.create_user(
        conn,
        email="split-name@example.com",
        name="Ada Lovelace",
        password_hash="x",
        tier="free",
        audience="base",
    )
    user = repo.get_user_by_email(conn, "split-name@example.com")
    assert user["first_name"] == "Ada"
    assert user["last_name"] == "Lovelace"


def test_create_user_single_word_name_has_empty_last_name(conn):
    repo.create_user(
        conn,
        email="single-name@example.com",
        name="Cher",
        password_hash="x",
        tier="free",
        audience="base",
    )
    user = repo.get_user_by_email(conn, "single-name@example.com")
    assert user["first_name"] == "Cher"
    assert user["last_name"] == ""


def test_set_name_updates_first_last_and_derived_name(conn):
    repo.create_user(
        conn,
        email="rename@example.com",
        name="Old Name",
        password_hash="x",
        tier="free",
        audience="base",
    )
    user = repo.get_user_by_email(conn, "rename@example.com")

    repo.set_name(conn, user["id"], "New", "Name")
    updated = repo.get_user_by_email(conn, "rename@example.com")
    assert updated["first_name"] == "New"
    assert updated["last_name"] == "Name"
    assert updated["name"] == "New Name"


def test_set_avatar_url_updates_column(conn):
    repo.create_user(
        conn,
        email="avatar@example.com",
        name="Avatar Test",
        password_hash="x",
        tier="free",
        audience="base",
    )
    user = repo.get_user_by_email(conn, "avatar@example.com")

    repo.set_avatar_url(conn, user["id"], "/static/avatars/1.png")
    updated = repo.get_user_by_email(conn, "avatar@example.com")
    assert updated["avatar_url"] == "/static/avatars/1.png"
