"""Waitlist (Plan D, S1): table, service, public routes."""

from __future__ import annotations

import pytest

import db
import waitlist_service as ws


def _memory_conn():
    return db.connect(":memory:")


def test_waitlist_table_exists_with_expected_columns():
    conn = _memory_conn()
    cols = {row[1] for row in conn.execute("PRAGMA table_info(waitlist)")}
    assert cols == {
        "id", "email", "apps", "lang", "consent_at",
        "confirm_token_hash", "confirmed_at", "created_at",
    }


def test_join_returns_token_and_stores_only_its_hash():
    conn = _memory_conn()
    token = ws.join(
        conn, email="  Ada@Example.org ", apps=["naforo", "kelen"], lang="it", consent=True
    )
    assert token and len(token) >= 32
    row = conn.execute(
        "SELECT email, apps, lang, confirm_token_hash, confirmed_at FROM waitlist"
    ).fetchone()
    assert row[0] == "ada@example.org"
    assert row[1] == "kelen,naforo"
    assert row[2] == "it"
    assert row[3] != token and len(row[3]) == 64
    assert row[4] is None


@pytest.mark.parametrize(
    "kwargs, code",
    [
        ({"email": "not-an-email"}, "invalid_email"),
        ({"email": "a@b.c" + "x" * 300}, "invalid_email"),
        ({"apps": ["pazuru"]}, "invalid_apps"),
        ({"consent": False}, "consent_required"),
    ],
)
def test_join_rejects_bad_input(kwargs, code):
    conn = _memory_conn()
    args = {"email": "a@example.org", "apps": ["naforo"], "lang": "en", "consent": True, **kwargs}
    with pytest.raises(ws.WaitlistError, match=code):
        ws.join(conn, **args)


def test_unknown_lang_falls_back_to_en():
    conn = _memory_conn()
    ws.join(conn, email="a@example.org", apps=[], lang="de", consent=True)
    assert conn.execute("SELECT lang FROM waitlist").fetchone()[0] == "en"


def test_rejoin_unconfirmed_rotates_token():
    conn = _memory_conn()
    first = ws.join(conn, email="a@example.org", apps=["naforo"], lang="en", consent=True)
    second = ws.join(conn, email="a@example.org", apps=["yiriba"], lang="fr", consent=True)
    assert first != second
    assert ws.confirm(conn, first) is False
    assert ws.confirm(conn, second) is True
    assert conn.execute("SELECT COUNT(*) FROM waitlist").fetchone()[0] == 1


def test_confirm_is_single_use_and_rejoin_after_confirm_returns_none():
    conn = _memory_conn()
    token = ws.join(conn, email="a@example.org", apps=[], lang="en", consent=True)
    assert ws.confirm(conn, token) is True
    assert ws.confirm(conn, token) is False
    assert ws.join(conn, email="a@example.org", apps=[], lang="en", consent=True) is None


def test_confirm_unknown_token():
    assert ws.confirm(_memory_conn(), "nope") is False
