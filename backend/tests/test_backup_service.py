"""Tests for backup_service.py (TI-A, foroba#151)."""

from __future__ import annotations

import io
import tarfile

import pytest

import backup_service


@pytest.fixture
def paths(tmp_path, monkeypatch):
    db_path = tmp_path / "foroba_identity.db"
    db_path.write_bytes(b"fake-sqlite-content")
    keys_dir = tmp_path / "keys"
    keys_dir.mkdir()
    priv = keys_dir / "jwt_private.pem"
    priv.write_bytes(b"fake-private-key")
    pub = keys_dir / "jwt_public.pem"
    pub.write_bytes(b"fake-public-key")

    monkeypatch.setattr(backup_service.settings, "auth_db_path", str(db_path))
    monkeypatch.setattr(backup_service.settings, "jwt_private_key_path", str(priv))
    monkeypatch.setattr(backup_service.settings, "jwt_public_key_path", str(pub))
    return db_path, priv, pub


def test_export_archive_contains_all_three_files(paths):
    archive = backup_service.export_archive()
    with tarfile.open(fileobj=io.BytesIO(archive), mode="r:gz") as tar:
        names = set(tar.getnames())
    assert names == {"foroba_identity.db", "jwt_private.pem", "jwt_public.pem"}


def test_import_archive_restores_files(paths):
    db_path, priv, _pub = paths
    archive = backup_service.export_archive()
    db_path.write_bytes(b"corrupted")
    priv.write_bytes(b"corrupted")

    result = backup_service.import_archive(archive)

    assert set(result["restored_files"]) == {
        "foroba_identity.db",
        "jwt_private.pem",
        "jwt_public.pem",
    }
    assert db_path.read_bytes() == b"fake-sqlite-content"
    assert priv.read_bytes() == b"fake-private-key"


def test_import_archive_rejects_unexpected_filename():
    buf = io.BytesIO()
    with tarfile.open(fileobj=buf, mode="w:gz") as tar:
        info = tarfile.TarInfo(name="../etc/passwd")
        payload = b"malicious"
        info.size = len(payload)
        tar.addfile(info, io.BytesIO(payload))

    with pytest.raises(ValueError, match="Unexpected file"):
        backup_service.import_archive(buf.getvalue())
