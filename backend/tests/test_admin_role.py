from fastapi import Depends, FastAPI
from fastapi.testclient import TestClient

from auth import keys
from auth.conn import get_conn
from auth.dependencies import get_current_user, require_admin
from auth.security import create_token
from config import settings
from db import connect, seed_mock_users


def make_app(admin_only: bool = False):
    app = FastAPI()
    dep = require_admin if admin_only else get_current_user

    @app.get("/protected")
    def protected(user: dict = Depends(dep)):
        return {"ok": True, "is_admin": user["is_admin"]}

    return app


def fresh_db(tmp_path):
    db_path = str(tmp_path / "test.db")
    conn = connect(db_path)
    seed_mock_users(conn)
    return conn, db_path


def test_is_admin_column_exists(tmp_path):
    conn, _ = fresh_db(tmp_path)
    row = conn.execute("SELECT is_admin FROM users LIMIT 1").fetchone()
    assert row is not None
    assert "is_admin" in dict(row)


def test_admin_seed_user_exists(tmp_path):
    conn, _ = fresh_db(tmp_path)
    row = conn.execute(
        "SELECT is_admin FROM users WHERE email = ?", ("admin@foroba.app",)
    ).fetchone()
    assert row is not None
    assert row["is_admin"] == 1


def test_require_admin_allows_admin(tmp_path):
    conn, _ = fresh_db(tmp_path)
    admin = dict(conn.execute(
        "SELECT * FROM users WHERE email = ?", ("admin@foroba.app",)
    ).fetchone())
    private_key, _, _ = keys.get_keypair(settings)
    token = create_token(
        admin["id"], private_key, 60,
        tier=admin["tier"], audience=admin["audience"], is_admin=bool(admin["is_admin"]),
    )
    app = make_app(admin_only=True)
    app.dependency_overrides[get_conn] = lambda: conn
    client = TestClient(app)
    resp = client.get("/protected", cookies={"suite_session": token})
    assert resp.status_code == 200


def test_require_admin_blocks_regular_user(tmp_path):
    conn, _ = fresh_db(tmp_path)
    user = dict(conn.execute(
        "SELECT * FROM users WHERE email = ?", ("demo@foroba.app",)
    ).fetchone())
    private_key, _, _ = keys.get_keypair(settings)
    token = create_token(
        user["id"], private_key, 60,
        tier=user["tier"], audience=user["audience"], is_admin=False,
    )
    app = make_app(admin_only=True)
    app.dependency_overrides[get_conn] = lambda: conn
    client = TestClient(app)
    resp = client.get("/protected", cookies={"suite_session": token})
    assert resp.status_code == 403
