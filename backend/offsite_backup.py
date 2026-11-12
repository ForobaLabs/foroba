"""Offsite upload of the encrypted suite backup to Cloudflare R2 (TI-E, foroba#172).

R2 is S3-compatible, so this uses `boto3`'s standard S3 client pointed at R2's
endpoint. The uploaded bytes are always already-encrypted (produced by
`backup_orchestrator.export_suite()`) — this module never sees plaintext.

No-ops when unconfigured, following the same convention as `GLITCHTIP_DSN`: an
empty `.env` means the feature is simply off, not an error.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import boto3

from config import settings


def is_configured() -> bool:
    return bool(
        settings.r2_account_id
        and settings.r2_access_key_id
        and settings.r2_secret_access_key
        and settings.r2_bucket
        and settings.backup_encryption_passphrase
    )


def _client():
    return boto3.client(
        "s3",
        endpoint_url=f"https://{settings.r2_account_id}.r2.cloudflarestorage.com",
        aws_access_key_id=settings.r2_access_key_id,
        aws_secret_access_key=settings.r2_secret_access_key,
    )


def upload_backup(data: bytes) -> str:
    """Upload the encrypted archive, returning the object key. Raises on failure —
    this is a scheduled write path, errors must surface (caught by the caller's
    logging + GlitchTip), never be swallowed."""
    key = f"backups/suite-{datetime.now(UTC).strftime('%Y%m%dT%H%M%SZ')}.bin"
    _client().put_object(Bucket=settings.r2_bucket, Key=key, Body=data)
    return key


def prune_backups(retention_days: int = 30, min_keep: int = 7) -> list[str]:
    """Delete archives older than `retention_days`, always keeping the newest `min_keep`
    (so a long outage of the backup job can never empty the bucket). Returns deleted keys."""
    client = _client()
    items: list[dict] = []
    token: str | None = None
    while True:
        kwargs = {"Bucket": settings.r2_bucket, "Prefix": "backups/"}
        if token:
            kwargs["ContinuationToken"] = token
        page = client.list_objects_v2(**kwargs)
        items.extend(page.get("Contents", []))
        token = page.get("NextContinuationToken")
        if not token:
            break
    items.sort(key=lambda o: o["LastModified"], reverse=True)
    cutoff = datetime.now(UTC) - timedelta(days=retention_days)
    stale = [o["Key"] for o in items[min_keep:] if o["LastModified"] < cutoff]
    for i in range(0, len(stale), 1000):
        client.delete_objects(
            Bucket=settings.r2_bucket,
            Delete={"Objects": [{"Key": k} for k in stale[i : i + 1000]]},
        )
    return stale
