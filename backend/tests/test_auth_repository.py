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


def test_create_user_defaults_mfa_enrollment_pending_false(conn):
    repo.create_user(
        conn, email="default-mfa@example.com", name="Default", password_hash="x"
    )
    user = repo.get_user_by_email(conn, "default-mfa@example.com")
    assert user["mfa_enrollment_pending"] == 0


def test_create_user_require_mfa_enrollment_sets_pending_true(conn):
    """foroba#173 — register() opts new self-service signups into forced MFA setup."""
    repo.create_user(
        conn,
        email="require-mfa@example.com",
        name="Require",
        password_hash="x",
        require_mfa_enrollment=True,
    )
    user = repo.get_user_by_email(conn, "require-mfa@example.com")
    assert user["mfa_enrollment_pending"] == 1


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


# ---------------------------------------------------------------------------
# foroba#185 — GL-10.1: invite codes + admin KPIs
# ---------------------------------------------------------------------------


def test_create_and_list_invite_codes(conn):
    admin = repo.create_user(
        conn, email="admin-invite@example.com", name="Admin", password_hash="x"
    )
    created = repo.create_invite_code(
        conn,
        code="ABCD-1234",
        note="beta batch",
        max_uses=3,
        expires_at=None,
        created_by_user_id=admin["id"],
    )
    assert created["code"] == "ABCD-1234"
    assert created["uses_count"] == 0

    codes = repo.list_invite_codes(conn)
    assert any(c["id"] == created["id"] for c in codes)


def test_revoke_invite_code_marks_revoked_and_is_idempotently_false(conn):
    admin = repo.create_user(
        conn, email="admin-revoke@example.com", name="Admin", password_hash="x"
    )
    created = repo.create_invite_code(
        conn, code="WXYZ-9999", note=None, max_uses=1, expires_at=None,
        created_by_user_id=admin["id"],
    )
    assert repo.revoke_invite_code(conn, created["id"]) is True
    assert repo.revoke_invite_code(conn, created["id"]) is False
    assert repo.revoke_invite_code(conn, 999999) is False


def test_redeem_invite_code_respects_max_uses_and_revocation(conn):
    admin = repo.create_user(
        conn, email="admin-redeem@example.com", name="Admin", password_hash="x"
    )
    repo.create_invite_code(
        conn, code="LIMIT-0001", note=None, max_uses=2, expires_at=None,
        created_by_user_id=admin["id"],
    )
    assert repo.redeem_invite_code(conn, "LIMIT-0001") is True
    assert repo.redeem_invite_code(conn, "LIMIT-0001") is True
    assert repo.redeem_invite_code(conn, "LIMIT-0001") is False  # exhausted
    assert repo.redeem_invite_code(conn, "NOSUCH-CODE") is False

    single = repo.create_invite_code(
        conn, code="REVOKE-0001", note=None, max_uses=5, expires_at=None,
        created_by_user_id=admin["id"],
    )
    repo.revoke_invite_code(conn, single["id"])
    assert repo.redeem_invite_code(conn, "REVOKE-0001") is False


def test_redeem_invite_code_respects_expiry(conn):
    admin = repo.create_user(
        conn, email="admin-expiry@example.com", name="Admin", password_hash="x"
    )
    repo.create_invite_code(
        conn, code="EXPIRED-01", note=None, max_uses=5, expires_at="2000-01-01T00:00:00",
        created_by_user_id=admin["id"],
    )
    assert repo.redeem_invite_code(conn, "EXPIRED-01") is False


def test_get_admin_kpis_counts(conn):
    admin = repo.create_user(
        conn, email="kpi-admin@example.com", name="Admin", password_hash="x"
    )
    conn.execute("UPDATE users SET is_admin = 1 WHERE id = ?", (admin["id"],))
    conn.commit()
    repo.create_user(
        conn, email="kpi-free@example.com", name="Free", password_hash="x",
        tier="free", audience="base",
    )
    repo.create_user(
        conn, email="kpi-premium@example.com", name="Premium", password_hash="x",
        tier="premium", audience="expert",
    )
    kpis = repo.get_admin_kpis(conn)
    assert kpis["total_users"] == 3
    assert kpis["admins"] == 1
    assert kpis["users_by_tier"]["free"] == 2
    assert kpis["users_by_tier"]["premium"] == 1
    assert kpis["users_by_audience"]["base"] == 2
    assert kpis["users_by_audience"]["expert"] == 1
    assert kpis["signups_last_7d"] == 3
    assert kpis["signups_last_30d"] == 3
    assert kpis["accounts_disabled"] == 0
