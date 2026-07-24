import io
import sqlite3

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from auth import repository as repo
from auth.dependencies import get_current_user
from auth.router import get_conn, router
from auth.security import hash_password
from db import init_schema


@pytest.fixture
def client(tmp_path, monkeypatch):
    monkeypatch.setenv("AVATAR_STORAGE_DIR", str(tmp_path))
    conn = sqlite3.connect(":memory:", check_same_thread=False)
    conn.row_factory = sqlite3.Row
    init_schema(conn)
    user = repo.create_user(
        conn, email="avatar-test@y.com", name="Avatar Test",
        password_hash=hash_password("password123"),
    )
    app = FastAPI()
    app.dependency_overrides[get_conn] = lambda: conn
    app.dependency_overrides[get_current_user] = lambda: repo.get_user_by_id(conn, user["id"])
    app.include_router(router)
    return TestClient(app), conn, user["id"]


def test_upload_valid_png_sets_avatar_url(client):
    test_client, conn, user_id = client
    png_bytes = b"\x89PNG\r\n\x1a\n" + b"\x00" * 100
    resp = test_client.post(
        "/auth/me/avatar",
        files={"file": ("avatar.png", io.BytesIO(png_bytes), "image/png")},
    )
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["avatar_url"].endswith(f"/static/avatars/{user_id}.png")
    updated = repo.get_user_by_id(conn, user_id)
    assert updated["avatar_url"] == body["avatar_url"]


def test_upload_rejects_wrong_content_type(client):
    test_client, _, _ = client
    resp = test_client.post(
        "/auth/me/avatar",
        files={"file": ("avatar.txt", io.BytesIO(b"not an image"), "text/plain")},
    )
    assert resp.status_code == 400


def test_upload_rejects_file_over_2mb(client):
    test_client, _, _ = client
    oversized = b"\x89PNG\r\n\x1a\n" + b"\x00" * (2 * 1024 * 1024 + 1)
    resp = test_client.post(
        "/auth/me/avatar",
        files={"file": ("big.png", io.BytesIO(oversized), "image/png")},
    )
    assert resp.status_code == 400
