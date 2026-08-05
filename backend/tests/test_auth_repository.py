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


def test_delete_user_removes_only_target_users_rows_and_never_touches_fx_rates(conn):
    """foroba#183 — GDPR Art. 17 erasure: seeds two users' worth of data across every
    Foroba-owned table, deletes user 1, and asserts only their rows are gone while
    user 2's rows and the global fx_rates table are untouched."""
    user1 = repo.create_user(conn, email="erase-me@example.com", name="Erase Me", password_hash="x")
    user2 = repo.create_user(conn, email="keep-me@example.com", name="Keep Me", password_hash="x")

    conn.execute(
        "INSERT INTO share_preferences (user_id, resource_type, shared) VALUES (?, 'portfolio', 1)",
        (user1["id"],),
    )
    conn.execute(
        "INSERT INTO share_preferences (user_id, resource_type, shared) VALUES (?, 'portfolio', 1)",
        (user2["id"],),
    )
    conn.execute(
        "INSERT INTO sandbox_conversations (user_id, session_id, role, content) "
        "VALUES (?, 's1', 'user', 'hi')",
        (str(user1["id"]),),
    )
    conn.execute(
        "INSERT INTO sandbox_conversations (user_id, session_id, role, content) "
        "VALUES (?, 's1', 'user', 'hi')",
        (str(user2["id"]),),
    )
    conn.execute(
        "INSERT INTO sandbox_user_context (user_id, context_text) VALUES (?, 'notes')",
        (str(user1["id"]),),
    )
    conn.execute(
        "INSERT INTO sandbox_user_context (user_id, context_text) VALUES (?, 'notes')",
        (str(user2["id"]),),
    )
    conn.execute(
        "INSERT INTO notification_dismissals (user_id, notif_key) VALUES (?, 'goal_reached:1')",
        (user1["id"],),
    )
    conn.execute(
        "INSERT INTO notification_dismissals (user_id, notif_key) VALUES (?, 'goal_reached:1')",
        (user2["id"],),
    )
    conn.execute(
        "INSERT INTO recurring_amount_baselines (user_id, pattern_id, last_amount_cents) "
        "VALUES (?, 1, 1000)",
        (user1["id"],),
    )
    conn.execute(
        "INSERT INTO recurring_amount_baselines (user_id, pattern_id, last_amount_cents) "
        "VALUES (?, 1, 1000)",
        (user2["id"],),
    )
    conn.execute(
        "INSERT INTO whatif_scenarios (created_by_user_id, name, horizon_months, params_json) "
        "VALUES (?, 'Plan A', 12, '{}')",
        (user1["id"],),
    )
    conn.execute(
        "INSERT INTO whatif_scenarios (created_by_user_id, name, horizon_months, params_json) "
        "VALUES (?, 'Plan A', 12, '{}')",
        (user2["id"],),
    )
    conn.execute(
        "INSERT INTO monthly_reports (user_id, year_month, trigger) "
        "VALUES (?, '2026-08', 'manual')",
        (user1["id"],),
    )
    conn.execute(
        "INSERT INTO monthly_reports (user_id, year_month, trigger) "
        "VALUES (?, '2026-08', 'manual')",
        (user2["id"],),
    )
    conn.execute(
        "INSERT INTO fx_rates (currency, rate_to_eur, rate_date) VALUES ('USD', 0.9, '2026-08-01')"
    )
    conn.execute(
        "INSERT INTO api_keys (user_id, label, key_prefix, secret_hash) "
        "VALUES (?, 'CLI', 'pfh_1', 'h1')",
        (user1["id"],),
    )
    conn.execute(
        "INSERT INTO api_keys (user_id, label, key_prefix, secret_hash) "
        "VALUES (?, 'CLI', 'pfh_2', 'h2')",
        (user2["id"],),
    )
    webhook1 = conn.execute(
        "INSERT INTO webhooks (user_id, target_url, signing_secret) VALUES (?, 'https://x', 's1')",
        (user1["id"],),
    ).lastrowid
    conn.execute(
        "INSERT INTO webhooks (user_id, target_url, signing_secret) VALUES (?, 'https://y', 's2')",
        (user2["id"],),
    )
    conn.execute(
        "INSERT INTO webhook_deliveries (webhook_id, event_key) VALUES (?, 'evt1')", (webhook1,)
    )
    conn.execute(
        "INSERT INTO recovery_codes (user_id, code_hash) VALUES (?, 'rc1')", (user1["id"],)
    )
    conn.execute(
        "INSERT INTO recovery_codes (user_id, code_hash) VALUES (?, 'rc2')", (user2["id"],)
    )
    conn.execute(
        "INSERT INTO email_otp_codes (user_id, code_hash, expires_at) "
        "VALUES (?, 'e1', '2099-01-01')",
        (user1["id"],),
    )
    conn.execute(
        "INSERT INTO email_otp_codes (user_id, code_hash, expires_at) "
        "VALUES (?, 'e2', '2099-01-01')",
        (user2["id"],),
    )
    conn.execute(
        "INSERT INTO webauthn_credentials (user_id, credential_id, public_key) "
        "VALUES (?, 'cred1', 'pk1')",
        (user1["id"],),
    )
    conn.execute(
        "INSERT INTO webauthn_credentials (user_id, credential_id, public_key) "
        "VALUES (?, 'cred2', 'pk2')",
        (user2["id"],),
    )
    conn.execute(
        "INSERT INTO webauthn_challenges (user_id, challenge, purpose) VALUES (?, 'chal1', 'auth')",
        (user1["id"],),
    )
    conn.execute(
        "INSERT INTO webauthn_challenges (user_id, challenge, purpose) VALUES (?, 'chal2', 'auth')",
        (user2["id"],),
    )
    repo.record_consent(
        conn,
        user_id=user1["id"],
        document_type="terms_of_service",
        document_version="2026-07-31",
        ip_address="127.0.0.1",
    )
    repo.record_consent(
        conn,
        user_id=user2["id"],
        document_type="terms_of_service",
        document_version="2026-07-31",
        ip_address="127.0.0.1",
    )
    conn.commit()

    repo.delete_user(conn, user1["id"])

    assert repo.get_user_by_id(conn, user1["id"]) is None
    assert repo.get_user_by_id(conn, user2["id"]) is not None
    tables_by_user_col = {
        "share_preferences": "user_id",
        "notification_dismissals": "user_id",
        "recurring_amount_baselines": "user_id",
        "monthly_reports": "user_id",
        "api_keys": "user_id",
        "webhooks": "user_id",
        "recovery_codes": "user_id",
        "email_otp_codes": "user_id",
        "webauthn_credentials": "user_id",
        "webauthn_challenges": "user_id",
        "consents": "user_id",
    }
    for table, col in tables_by_user_col.items():
        assert conn.execute(
            f"SELECT count(*) FROM {table} WHERE {col} = ?", (user1["id"],)
        ).fetchone()[0] == 0
        assert conn.execute(
            f"SELECT count(*) FROM {table} WHERE {col} = ?", (user2["id"],)
        ).fetchone()[0] == 1
    for table in ("sandbox_conversations", "sandbox_user_context"):
        assert conn.execute(
            f"SELECT count(*) FROM {table} WHERE user_id = ?", (str(user1["id"]),)
        ).fetchone()[0] == 0
        assert conn.execute(
            f"SELECT count(*) FROM {table} WHERE user_id = ?", (str(user2["id"]),)
        ).fetchone()[0] == 1
    assert conn.execute(
        "SELECT count(*) FROM whatif_scenarios WHERE created_by_user_id = ?", (user1["id"],)
    ).fetchone()[0] == 0
    assert conn.execute(
        "SELECT count(*) FROM whatif_scenarios WHERE created_by_user_id = ?", (user2["id"],)
    ).fetchone()[0] == 1
    assert conn.execute("SELECT count(*) FROM webhook_deliveries").fetchone()[0] == 0
    assert conn.execute("SELECT count(*) FROM fx_rates").fetchone()[0] == 1
