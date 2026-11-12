"""Tests for offsite_backup.py (TI-E, foroba#172). boto3 is fully mocked — no
real network, no real R2 credentials."""

from __future__ import annotations

import pytest

import offsite_backup as ob


def _clear_config(monkeypatch) -> None:
    for attr in (
        "r2_account_id",
        "r2_access_key_id",
        "r2_secret_access_key",
        "r2_bucket",
        "backup_encryption_passphrase",
    ):
        monkeypatch.setattr(ob.settings, attr, "")


def _set_config(monkeypatch) -> None:
    monkeypatch.setattr(ob.settings, "r2_account_id", "acct123")
    monkeypatch.setattr(ob.settings, "r2_access_key_id", "key123")
    monkeypatch.setattr(ob.settings, "r2_secret_access_key", "secret123")
    monkeypatch.setattr(ob.settings, "r2_bucket", "pfh-backups")
    monkeypatch.setattr(ob.settings, "backup_encryption_passphrase", "correct-horse")


def test_is_configured_false_when_any_var_missing(monkeypatch):
    _clear_config(monkeypatch)
    assert ob.is_configured() is False

    _set_config(monkeypatch)
    monkeypatch.setattr(ob.settings, "r2_bucket", "")
    assert ob.is_configured() is False


def test_is_configured_true_when_all_vars_present(monkeypatch):
    _set_config(monkeypatch)
    assert ob.is_configured() is True


class _FakeS3Client:
    def __init__(self) -> None:
        self.calls: list[dict] = []

    def put_object(self, **kwargs) -> None:
        self.calls.append(kwargs)


def test_upload_backup_puts_object_with_expected_bucket_and_prefix(monkeypatch):
    _set_config(monkeypatch)
    fake_client = _FakeS3Client()
    captured_kwargs: dict = {}

    def fake_boto3_client(service: str, **kwargs) -> _FakeS3Client:
        captured_kwargs.update(kwargs)
        assert service == "s3"
        return fake_client

    monkeypatch.setattr(ob.boto3, "client", fake_boto3_client)

    key = ob.upload_backup(b"encrypted-bytes")

    assert captured_kwargs["endpoint_url"] == "https://acct123.r2.cloudflarestorage.com"
    assert captured_kwargs["aws_access_key_id"] == "key123"
    assert captured_kwargs["aws_secret_access_key"] == "secret123"
    assert len(fake_client.calls) == 1
    assert fake_client.calls[0]["Bucket"] == "pfh-backups"
    assert fake_client.calls[0]["Body"] == b"encrypted-bytes"
    assert key == fake_client.calls[0]["Key"]
    assert key.startswith("backups/suite-") and key.endswith(".bin")


def test_upload_backup_propagates_client_errors(monkeypatch):
    _set_config(monkeypatch)

    class _FailingClient:
        def put_object(self, **kwargs) -> None:
            raise RuntimeError("R2 unreachable")

    monkeypatch.setattr(ob.boto3, "client", lambda *a, **kw: _FailingClient())

    with pytest.raises(RuntimeError, match="R2 unreachable"):
        ob.upload_backup(b"data")


def _obj(key: str, days_old: int):
    from datetime import UTC, datetime, timedelta

    return {"Key": key, "LastModified": datetime.now(UTC) - timedelta(days=days_old)}


def test_prune_deletes_only_objects_older_than_retention(monkeypatch):
    from unittest.mock import MagicMock

    _set_config(monkeypatch)
    client = MagicMock()
    objs = [_obj(f"backups/suite-{d}.bin", d) for d in (0, 1, 2, 3, 4, 5, 6, 7, 40, 90)]
    client.list_objects_v2.return_value = {"Contents": objs}
    monkeypatch.setattr(ob, "_client", lambda: client)

    deleted = ob.prune_backups(retention_days=30, min_keep=7)

    assert sorted(deleted) == ["backups/suite-40.bin", "backups/suite-90.bin"]
    sent = client.delete_objects.call_args.kwargs["Delete"]["Objects"]
    assert sorted(o["Key"] for o in sent) == sorted(deleted)


def test_prune_never_drops_below_min_keep(monkeypatch):
    from unittest.mock import MagicMock

    _set_config(monkeypatch)
    client = MagicMock()
    # Backups stopped for months: everything is "old", but the newest 7 must survive.
    objs = [_obj(f"backups/suite-{d}.bin", d) for d in range(100, 110)]
    client.list_objects_v2.return_value = {"Contents": objs}
    monkeypatch.setattr(ob, "_client", lambda: client)

    deleted = ob.prune_backups(retention_days=30, min_keep=7)

    assert len(deleted) == 3
    assert "backups/suite-100.bin" not in deleted


def test_prune_noop_when_nothing_to_delete(monkeypatch):
    from unittest.mock import MagicMock

    _set_config(monkeypatch)
    client = MagicMock()
    client.list_objects_v2.return_value = {"Contents": [_obj("backups/suite-1.bin", 1)]}
    monkeypatch.setattr(ob, "_client", lambda: client)

    assert ob.prune_backups() == []
    client.delete_objects.assert_not_called()
