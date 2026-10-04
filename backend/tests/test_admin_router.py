import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from admin_router import router as admin_router
from auth.conn import get_conn
from auth.dependencies import get_current_user
from db import connect, seed_mock_users
from settings_store import init_settings


@pytest.fixture
def setup(tmp_path):
    db_path = str(tmp_path / "test.db")
    conn = connect(db_path)
    seed_mock_users(conn)
    init_settings(conn)

    admin_user = dict(
        conn.execute("SELECT * FROM users WHERE email = ?", ("admin@foroba.app",)).fetchone()
    )
    regular_user = dict(
        conn.execute("SELECT * FROM users WHERE email = ?", ("demo@foroba.app",)).fetchone()
    )

    app = FastAPI()
    app.include_router(admin_router)
    app.dependency_overrides[get_conn] = lambda: conn

    return TestClient(app), conn, admin_user, regular_user


def test_get_settings_public_no_auth(setup):
    tc, _conn, _, _ = setup
    resp = tc.get("/jeli/admin/settings")
    assert resp.status_code == 200
    data = resp.json()
    assert "premium_gating_enabled" in data


def test_get_admin_settings_requires_admin(setup):
    tc, _conn, _, regular = setup
    tc.app.dependency_overrides[get_current_user] = lambda: regular
    resp = tc.get("/admin/settings")
    assert resp.status_code == 403


def test_get_admin_settings_admin_ok(setup):
    tc, _conn, admin, _ = setup
    tc.app.dependency_overrides[get_current_user] = lambda: admin
    resp = tc.get("/admin/settings")
    assert resp.status_code == 200


def test_patch_admin_setting(setup):
    tc, _conn, admin, _ = setup
    tc.app.dependency_overrides[get_current_user] = lambda: admin
    resp = tc.patch(
        "/admin/settings/premium_gating_enabled",
        json={"value": "true"},
    )
    assert resp.status_code == 200
    resp2 = tc.get("/jeli/admin/settings")
    assert resp2.json()["premium_gating_enabled"] == "true"


def test_patch_admin_setting_invalidates_downstream_caches(setup, monkeypatch):
    """PATCH must best-effort notify Pazuru/Tsumi to drop their cached
    settings snapshot, so a toggle+restore doesn't leave either app serving a
    stale value for up to their SettingsCache TTL (confirmed live 2026-09-17
    as the root cause of a false 402 on Tsumi shortly after a Foroba admin
    premium_gating_enabled toggle+restore)."""
    import admin_router
    from config import settings

    monkeypatch.setattr(settings, "internal_api_token", "t", raising=False)
    calls = []
    monkeypatch.setattr(admin_router.httpx, "post", lambda url, **kw: calls.append(url))

    tc, _conn, admin, _ = setup
    tc.app.dependency_overrides[get_current_user] = lambda: admin
    resp = tc.patch("/admin/settings/premium_gating_enabled", json={"value": "true"})

    assert resp.status_code == 200
    assert len(calls) == 2
    assert any(url.endswith("/jeli/settings-cache/invalidate") and "8000" in url for url in calls)
    assert any(url.endswith("/jeli/settings-cache/invalidate") and "8050" in url for url in calls)


def test_patch_admin_setting_never_raises_when_downstream_unreachable(setup, monkeypatch):
    """The invalidation call must never surface as a 500 -- same resilience
    posture as the polling endpoint it mirrors."""
    import admin_router
    from config import settings

    monkeypatch.setattr(settings, "internal_api_token", "t", raising=False)

    def _raise(url, **kw):
        raise admin_router.httpx.ConnectError("connection refused")

    monkeypatch.setattr(admin_router.httpx, "post", _raise)

    tc, _conn, admin, _ = setup
    tc.app.dependency_overrides[get_current_user] = lambda: admin
    resp = tc.patch("/admin/settings/premium_gating_enabled", json={"value": "true"})
    assert resp.status_code == 200


def test_patch_invalid_value_returns_422(setup):
    tc, _conn, admin, _ = setup
    tc.app.dependency_overrides[get_current_user] = lambda: admin
    resp = tc.patch(
        "/admin/settings/premium_gating_enabled",
        json={"value": "yes"},
    )
    assert resp.status_code == 422


def test_get_admin_users_returns_list(setup):
    tc, _conn, admin, _ = setup
    tc.app.dependency_overrides[get_current_user] = lambda: admin
    resp = tc.get("/admin/users")
    assert resp.status_code == 200
    users = resp.json()
    assert isinstance(users, list)
    assert any(u["email"] == "admin@foroba.app" for u in users)


def test_get_admin_users_tolerates_malformed_legacy_email(setup):
    """FOR-D05: a legacy row inserted out-of-band (email='ci@bearer.test',
    rejected by EmailStr as a reserved TLD) must not 500 the whole list."""
    tc, conn, admin, _ = setup
    tc.app.dependency_overrides[get_current_user] = lambda: admin

    admin_row = dict(conn.execute("SELECT * FROM users WHERE id = ?", (admin["id"],)).fetchone())
    bad_row = dict(admin_row)
    bad_row["email"] = "ci@bearer.test"
    bad_row["name"] = "Legacy CI row"
    bad_row["is_admin"] = 0
    cols = [c for c in admin_row if c != "id"]
    conn.execute(
        f"INSERT INTO users ({','.join(cols)}) VALUES ({','.join('?' for _ in cols)})",
        [bad_row[c] for c in cols],
    )
    conn.commit()

    resp = tc.get("/admin/users")
    assert resp.status_code == 200
    users = resp.json()
    emails = [u["email"] for u in users]
    assert "admin@foroba.app" in emails
    assert "ci@bearer.test" in emails


def test_export_backup_requires_admin(setup):
    tc, _conn, _, regular = setup
    tc.app.dependency_overrides[get_current_user] = lambda: regular
    resp = tc.post("/admin/backup/export-suite", json={"passphrase": "pw"})
    assert resp.status_code == 403


def test_export_backup_calls_orchestrator(setup, monkeypatch):
    import admin_router

    tc, _conn, admin, _ = setup
    tc.app.dependency_overrides[get_current_user] = lambda: admin

    async def _fake_export_suite(passphrase, cookie):
        assert passphrase == "pw"
        return b"encrypted-bytes"

    monkeypatch.setattr(admin_router.backup_orchestrator, "export_suite", _fake_export_suite)
    resp = tc.post("/admin/backup/export-suite", json={"passphrase": "pw"})
    assert resp.status_code == 200
    assert resp.content == b"encrypted-bytes"


def test_import_backup_calls_orchestrator(setup, monkeypatch):
    import admin_router

    tc, _conn, admin, _ = setup
    tc.app.dependency_overrides[get_current_user] = lambda: admin

    async def _fake_import_suite(encrypted, passphrase, cookie):
        assert passphrase == "pw"
        assert encrypted == b"uploaded-bytes"
        return {"foroba": {"restored_files": []}, "pazuru": {}, "tsumi": {}}

    monkeypatch.setattr(admin_router.backup_orchestrator, "import_suite", _fake_import_suite)
    resp = tc.post(
        "/admin/backup/import-suite",
        data={"passphrase": "pw"},
        files={"file": ("backup.pfhbak", b"uploaded-bytes", "application/octet-stream")},
    )
    assert resp.status_code == 200
    assert resp.json()["foroba"]["restored_files"] == []


def test_disable_account_requires_admin(setup):
    tc, _conn, _, regular = setup
    tc.app.dependency_overrides[get_current_user] = lambda: regular
    resp = tc.patch(f"/admin/users/{regular['id']}/disabled", json={"disabled": True})
    assert resp.status_code == 403


def test_admin_can_disable_and_enable_another_account(setup):
    tc, _conn, admin, regular = setup
    tc.app.dependency_overrides[get_current_user] = lambda: admin

    resp = tc.patch(f"/admin/users/{regular['id']}/disabled", json={"disabled": True})
    assert resp.status_code == 200
    assert resp.json()["account_disabled"] is True

    resp2 = tc.patch(f"/admin/users/{regular['id']}/disabled", json={"disabled": False})
    assert resp2.status_code == 200
    assert resp2.json()["account_disabled"] is False


def test_admin_cannot_disable_own_account(setup):
    tc, _conn, admin, _ = setup
    tc.app.dependency_overrides[get_current_user] = lambda: admin
    resp = tc.patch(f"/admin/users/{admin['id']}/disabled", json={"disabled": True})
    assert resp.status_code == 400


def test_disable_account_unknown_user_returns_404(setup):
    tc, _conn, admin, _ = setup
    tc.app.dependency_overrides[get_current_user] = lambda: admin
    resp = tc.patch("/admin/users/999999/disabled", json={"disabled": True})
    assert resp.status_code == 404


def test_import_backup_wrong_passphrase_returns_400(setup, monkeypatch):
    import admin_router

    tc, _conn, admin, _ = setup
    tc.app.dependency_overrides[get_current_user] = lambda: admin

    async def _fake_import_suite(encrypted, passphrase, cookie):
        raise admin_router.backup_orchestrator.InvalidPassphrase("bad pw")

    monkeypatch.setattr(admin_router.backup_orchestrator, "import_suite", _fake_import_suite)
    resp = tc.post(
        "/admin/backup/import-suite",
        data={"passphrase": "wrong"},
        files={"file": ("backup.pfhbak", b"x", "application/octet-stream")},
    )
    assert resp.status_code == 400


# ---------------------------------------------------------------------------
# foroba#185 — GL-10.1: KPIs + invite-code management
# ---------------------------------------------------------------------------


def test_get_kpis_requires_admin(setup):
    tc, _conn, _, regular = setup
    tc.app.dependency_overrides[get_current_user] = lambda: regular
    resp = tc.get("/admin/kpis")
    assert resp.status_code == 403


def test_get_kpis_returns_counts(setup):
    tc, _conn, admin, _ = setup
    tc.app.dependency_overrides[get_current_user] = lambda: admin
    resp = tc.get("/admin/kpis")
    assert resp.status_code == 200
    body = resp.json()
    assert body["total_users"] >= 4  # 4 seeded mock users
    assert "free" in body["users_by_tier"]
    assert body["admins"] >= 1


def test_create_invite_code_requires_admin(setup):
    tc, _conn, _, regular = setup
    tc.app.dependency_overrides[get_current_user] = lambda: regular
    resp = tc.post("/admin/invite-codes", json={})
    assert resp.status_code == 403


def test_create_and_list_invite_codes(setup):
    tc, _conn, admin, _ = setup
    tc.app.dependency_overrides[get_current_user] = lambda: admin
    resp = tc.post("/admin/invite-codes", json={"note": "beta batch 1", "max_uses": 5})
    assert resp.status_code == 201
    created = resp.json()
    assert created["note"] == "beta batch 1"
    assert created["max_uses"] == 5
    assert created["uses_count"] == 0
    assert "-" in created["code"]

    resp2 = tc.get("/admin/invite-codes")
    assert resp2.status_code == 200
    assert any(c["id"] == created["id"] for c in resp2.json())


def test_revoke_invite_code(setup):
    tc, _conn, admin, _ = setup
    tc.app.dependency_overrides[get_current_user] = lambda: admin
    created = tc.post("/admin/invite-codes", json={}).json()

    resp = tc.delete(f"/admin/invite-codes/{created['id']}")
    assert resp.status_code == 204

    codes = tc.get("/admin/invite-codes").json()
    revoked = next(c for c in codes if c["id"] == created["id"])
    assert revoked["revoked_at"] is not None


def test_revoke_unknown_invite_code_returns_404(setup):
    tc, _conn, admin, _ = setup
    tc.app.dependency_overrides[get_current_user] = lambda: admin
    resp = tc.delete("/admin/invite-codes/999999")
    assert resp.status_code == 404
