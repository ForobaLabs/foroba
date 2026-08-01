"""Tests for backup_orchestrator.py (TI-A, foroba#151). Pazuru/Tsumi's HTTP
boundary is mocked, same pattern as tests/test_markets_service.py."""

from __future__ import annotations

import asyncio
import io
import tarfile
from typing import Any

import pytest

import backup_orchestrator as orch


def _mini_tar(name: str, content: bytes) -> bytes:
    buf = io.BytesIO()
    with tarfile.open(fileobj=buf, mode="w:gz") as tar:
        info = tarfile.TarInfo(name=name)
        info.size = len(content)
        tar.addfile(info, io.BytesIO(content))
    return buf.getvalue()


class _FakeResponse:
    def __init__(self, content: bytes, status: int = 200, json_body: dict | None = None) -> None:
        self.content = content
        self.status_code = status
        self._json_body = json_body or {}

    def json(self) -> dict[str, Any]:
        return self._json_body

    def raise_for_status(self) -> None:
        if self.status_code >= 400:
            raise RuntimeError(f"HTTP {self.status_code}")


class _FakeClient:
    def __init__(
        self, get_routes: dict[str, bytes], post_routes: dict[str, dict] | None = None
    ) -> None:
        self._get_routes = get_routes
        self._post_routes = post_routes or {}

    async def __aenter__(self) -> _FakeClient:
        return self

    async def __aexit__(self, *exc: Any) -> None:
        return None

    async def get(self, url: str, **kwargs: Any) -> _FakeResponse:
        for needle, content in self._get_routes.items():
            if needle in url:
                return _FakeResponse(content)
        raise RuntimeError(f"unrouted GET: {url}")

    async def post(self, url: str, **kwargs: Any) -> _FakeResponse:
        for needle, body in self._post_routes.items():
            if needle in url:
                return _FakeResponse(b"", json_body=body)
        raise RuntimeError(f"unrouted POST: {url}")


def test_export_suite_bundles_and_encrypts(monkeypatch):
    monkeypatch.setattr(orch.settings, "pazuru_api_url", "http://pazuru-host")
    monkeypatch.setattr(orch.settings, "tsumi_api_url", "http://tsumi-host")
    monkeypatch.setattr(
        orch, "export_archive", lambda: _mini_tar("foroba_identity.db", b"foroba-data")
    )
    pazuru_blob = _mini_tar("pazuru.db", b"pazuru-data")
    tsumi_blob = _mini_tar("tsumi.duckdb", b"tsumi-data")
    monkeypatch.setattr(
        orch.httpx,
        "AsyncClient",
        lambda *a, **kw: _FakeClient({"pazuru": pazuru_blob, "tsumi": tsumi_blob}),
    )

    encrypted = asyncio.run(orch.export_suite("correct-horse-battery-staple", cookie="fake-cookie"))
    assert isinstance(encrypted, bytes) and len(encrypted) > 16  # salt prefix + ciphertext

    decrypted = orch.decrypt_archive(encrypted, "correct-horse-battery-staple")
    with tarfile.open(fileobj=io.BytesIO(decrypted), mode="r:") as tar:
        names = set(tar.getnames())
    assert names == {"manifest.json", "foroba.tar.gz", "pazuru.tar.gz", "tsumi.tar.gz"}


def test_decrypt_archive_wrong_passphrase_raises(monkeypatch):
    monkeypatch.setattr(orch.settings, "pazuru_api_url", "http://pazuru-host")
    monkeypatch.setattr(orch.settings, "tsumi_api_url", "http://tsumi-host")
    monkeypatch.setattr(
        orch, "export_archive", lambda: _mini_tar("foroba_identity.db", b"foroba-data")
    )
    monkeypatch.setattr(
        orch.httpx,
        "AsyncClient",
        lambda *a, **kw: _FakeClient(
            {
                "pazuru": _mini_tar("pazuru.db", b"p"),
                "tsumi": _mini_tar("tsumi.duckdb", b"t"),
            }
        ),
    )
    encrypted = asyncio.run(orch.export_suite("right-passphrase", cookie="fake-cookie"))

    with pytest.raises(orch.InvalidPassphrase):
        orch.decrypt_archive(encrypted, "wrong-passphrase")


def test_import_suite_forwards_to_pazuru_and_tsumi(monkeypatch):
    monkeypatch.setattr(orch.settings, "pazuru_api_url", "http://pazuru-host")
    monkeypatch.setattr(orch.settings, "tsumi_api_url", "http://tsumi-host")
    monkeypatch.setattr(
        orch, "export_archive", lambda: _mini_tar("foroba_identity.db", b"foroba-data")
    )
    pazuru_blob = _mini_tar("pazuru.db", b"pazuru-data")
    tsumi_blob = _mini_tar("tsumi.duckdb", b"tsumi-data")
    monkeypatch.setattr(
        orch.httpx,
        "AsyncClient",
        lambda *a, **kw: _FakeClient(
            {"pazuru": pazuru_blob, "tsumi": tsumi_blob},
            post_routes={
                "pazuru": {"restored_files": ["pazuru.db"], "restart_required": True},
                "tsumi": {"restored_files": ["tsumi.duckdb"], "restart_required": True},
            },
        ),
    )
    encrypted = asyncio.run(orch.export_suite("pw", cookie="fake-cookie"))

    imported_local: list[bytes] = []
    monkeypatch.setattr(
        orch,
        "import_archive",
        lambda data: (
            imported_local.append(data)
            or {"restored_files": ["foroba_identity.db"], "restart_required": True}
        ),
    )

    result = asyncio.run(orch.import_suite(encrypted, "pw", cookie="fake-cookie"))

    assert result["foroba"]["restored_files"] == ["foroba_identity.db"]
    assert result["pazuru"]["restored_files"] == ["pazuru.db"]
    assert result["tsumi"]["restored_files"] == ["tsumi.duckdb"]
    assert len(imported_local) == 1
