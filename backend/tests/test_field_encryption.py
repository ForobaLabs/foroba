"""Field-level Fernet encryption tests (foroba#186 / GL-8.2).

Covers:
- sandbox_user_context.context_text
- monthly_reports.narrative_text + context_snapshot_json
- whatif_scenarios.params_json
- users.totp_secret (via auth.repository)

Each test verifies:
1. The raw DB value is encrypted (ciphertext, not plaintext).
2. The read-path function returns the original plaintext.
3. Migration safety: legacy plaintext values are returned as-is.
"""

from __future__ import annotations

import json
import sqlite3

import pytest

import auth.repository as repo
from chat_crypto import is_encrypted
from db import (
    create_whatif_scenario,
    get_sandbox_user_context,
    get_whatif_scenario,
    init_schema,
    list_monthly_reports,
    list_whatif_scenarios,
    update_monthly_report_result,
    update_sandbox_user_context,
)

# ---------------------------------------------------------------------------
# Fixture
# ---------------------------------------------------------------------------

@pytest.fixture
def conn():
    c = sqlite3.connect(":memory:", check_same_thread=False)
    c.row_factory = sqlite3.Row
    init_schema(c)
    return c


@pytest.fixture
def user_id(conn) -> int:
    cur = conn.execute(
        "INSERT INTO users (email, name, password_hash) VALUES (?, ?, ?)",
        ("enc_test@example.com", "Enc Test", "hash"),
    )
    conn.commit()
    return cur.lastrowid


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _raw(conn: sqlite3.Connection, table: str, col: str, where: str, val) -> str | None:
    """Read a raw column value directly from the DB (bypassing any decrypt layer)."""
    return conn.execute(f"SELECT {col} FROM {table} WHERE {where} = ?", (val,)).fetchone()[col]


# ---------------------------------------------------------------------------
# sandbox_user_context.context_text
# ---------------------------------------------------------------------------

class TestSandboxUserContextEncryption:
    def test_stored_value_is_encrypted(self, conn, user_id):
        update_sandbox_user_context(conn, str(user_id), "My financial context")
        raw = _raw(conn, "sandbox_user_context", "context_text", "user_id", str(user_id))
        assert is_encrypted(raw), "context_text must be ciphertext in DB"

    def test_read_returns_plaintext(self, conn, user_id):
        update_sandbox_user_context(conn, str(user_id), "My financial context")
        assert get_sandbox_user_context(conn, str(user_id)) == "My financial context"

    def test_update_overwrites_encrypted(self, conn, user_id):
        update_sandbox_user_context(conn, str(user_id), "first")
        update_sandbox_user_context(conn, str(user_id), "second")
        assert get_sandbox_user_context(conn, str(user_id)) == "second"

    def test_migration_plaintext_returned_as_is(self, conn, user_id):
        """Legacy plaintext row is read back without error."""
        conn.execute(
            "INSERT INTO sandbox_user_context (user_id, context_text) VALUES (?, ?)",
            (str(user_id), "plain legacy text"),
        )
        conn.commit()
        assert get_sandbox_user_context(conn, str(user_id)) == "plain legacy text"

    def test_missing_user_returns_empty_string(self, conn):
        assert get_sandbox_user_context(conn, "99999") == ""


# ---------------------------------------------------------------------------
# whatif_scenarios.params_json
# ---------------------------------------------------------------------------

class TestWhatIfEncryption:
    def _create(self, conn, user_id, params=None):
        return create_whatif_scenario(
            conn,
            created_by_user_id=user_id,
            household_id=None,
            name="Test Scenario",
            horizon_months=12,
            params_json=json.dumps(params or {"income": 3000, "expenses": 1500}),
        )

    def test_stored_params_json_is_encrypted(self, conn, user_id):
        row = self._create(conn, user_id)
        raw = _raw(conn, "whatif_scenarios", "params_json", "id", row["id"])
        assert is_encrypted(raw), "params_json must be ciphertext in DB"

    def test_read_returns_plaintext(self, conn, user_id):
        params = {"income": 3000, "expenses": 1500}
        row = self._create(conn, user_id, params)
        assert json.loads(row["params_json"]) == params

    def test_list_decrypts_all(self, conn, user_id):
        self._create(conn, user_id, {"a": 1})
        self._create(conn, user_id, {"b": 2})
        rows = list_whatif_scenarios(conn, user_id=user_id, household_id=None)
        assert len(rows) == 2
        for r in rows:
            assert not is_encrypted(r["params_json"]), "list must return plaintext"

    def test_get_decrypts(self, conn, user_id):
        created = self._create(conn, user_id)
        fetched = get_whatif_scenario(
            conn, created["id"], user_id=user_id, household_id=None
        )
        assert fetched is not None
        assert json.loads(fetched["params_json"]) == {"income": 3000, "expenses": 1500}

    def test_migration_plaintext_params_returned_as_is(self, conn, user_id):
        """Direct DB insert of plaintext params_json is returned correctly."""
        conn.execute(
            "INSERT INTO whatif_scenarios "
            "(created_by_user_id, name, horizon_months, params_json) VALUES (?, ?, ?, ?)",
            (user_id, "Legacy", 6, '{"legacy": true}'),
        )
        conn.commit()
        rows = list_whatif_scenarios(conn, user_id=user_id, household_id=None)
        legacy = next(r for r in rows if r["name"] == "Legacy")
        assert json.loads(legacy["params_json"]) == {"legacy": True}


# ---------------------------------------------------------------------------
# monthly_reports.narrative_text + context_snapshot_json
# ---------------------------------------------------------------------------

class TestMonthlyReportEncryption:
    def _create_report(self, conn, user_id) -> int:
        cur = conn.execute(
            "INSERT INTO monthly_reports (user_id, year_month, trigger, status) "
            "VALUES (?, ?, ?, 'generating')",
            (user_id, "2026-08", "manual"),
        )
        conn.commit()
        return cur.lastrowid

    def test_narrative_is_encrypted_in_db(self, conn, user_id):
        report_id = self._create_report(conn, user_id)
        update_monthly_report_result(
            conn,
            report_id,
            status="done",
            narrative_text="Great month overall.",
            context_snapshot_json='{"balance": 5000}',
            error_message=None,
            attempt_count=1,
        )
        raw_narrative = _raw(conn, "monthly_reports", "narrative_text", "id", report_id)
        raw_context = _raw(conn, "monthly_reports", "context_snapshot_json", "id", report_id)
        assert is_encrypted(raw_narrative), "narrative_text must be ciphertext in DB"
        assert is_encrypted(raw_context), "context_snapshot_json must be ciphertext in DB"

    def test_read_returns_plaintext(self, conn, user_id):
        report_id = self._create_report(conn, user_id)
        updated = update_monthly_report_result(
            conn,
            report_id,
            status="done",
            narrative_text="Great month.",
            context_snapshot_json='{"balance": 5000}',
            error_message=None,
            attempt_count=1,
        )
        assert updated["narrative_text"] == "Great month."
        assert updated["context_snapshot_json"] == '{"balance": 5000}'

    def test_list_decrypts_all(self, conn, user_id):
        report_id = self._create_report(conn, user_id)
        update_monthly_report_result(
            conn, report_id, status="done",
            narrative_text="Summary.", context_snapshot_json=None,
            error_message=None, attempt_count=1,
        )
        reports = list_monthly_reports(conn, user_id=user_id)
        assert len(reports) == 1
        assert reports[0]["narrative_text"] == "Summary."

    def test_null_fields_remain_null(self, conn, user_id):
        report_id = self._create_report(conn, user_id)
        updated = update_monthly_report_result(
            conn, report_id, status="error",
            narrative_text=None, context_snapshot_json=None,
            error_message="LLM timeout", attempt_count=1,
        )
        assert updated["narrative_text"] is None
        assert updated["context_snapshot_json"] is None

    def test_migration_plaintext_narrative_returned_as_is(self, conn, user_id):
        """Legacy plaintext narrative_text is returned without error."""
        report_id = self._create_report(conn, user_id)
        conn.execute(
            "UPDATE monthly_reports SET narrative_text = ?, status = 'done' WHERE id = ?",
            ("legacy plain text", report_id),
        )
        conn.commit()
        reports = list_monthly_reports(conn, user_id=user_id)
        assert reports[0]["narrative_text"] == "legacy plain text"


# ---------------------------------------------------------------------------
# users.totp_secret (via auth.repository)
# ---------------------------------------------------------------------------

class TestTotpSecretEncryption:
    def test_stored_secret_is_encrypted(self, conn, user_id):
        repo.set_totp_secret(conn, user_id, "JBSWY3DPEHPK3PXP")
        raw = _raw(conn, "users", "totp_secret", "id", user_id)
        assert is_encrypted(raw), "totp_secret must be ciphertext in DB"

    def test_get_user_by_id_returns_plaintext(self, conn, user_id):
        repo.set_totp_secret(conn, user_id, "JBSWY3DPEHPK3PXP")
        user = repo.get_user_by_id(conn, user_id)
        assert user["totp_secret"] == "JBSWY3DPEHPK3PXP"

    def test_get_user_by_email_returns_plaintext(self, conn, user_id):
        repo.set_totp_secret(conn, user_id, "ABCDE67890FGHIJK")
        user = repo.get_user_by_email(conn, "enc_test@example.com")
        assert user["totp_secret"] == "ABCDE67890FGHIJK"

    def test_list_all_users_decrypts(self, conn, user_id):
        repo.set_totp_secret(conn, user_id, "MYSECRET1234567A")
        users = repo.list_all_users(conn)
        target = next(u for u in users if u["id"] == user_id)
        assert target["totp_secret"] == "MYSECRET1234567A"

    def test_migration_plaintext_secret_returned_as_is(self, conn, user_id):
        """Legacy plaintext totp_secret (before encryption was enabled) works on read."""
        conn.execute(
            "UPDATE users SET totp_secret = ? WHERE id = ?", ("LEGACY_PLAIN_SECRET", user_id)
        )
        conn.commit()
        user = repo.get_user_by_id(conn, user_id)
        assert user["totp_secret"] == "LEGACY_PLAIN_SECRET"

    def test_null_secret_returns_none(self, conn, user_id):
        user = repo.get_user_by_id(conn, user_id)
        assert user["totp_secret"] is None
