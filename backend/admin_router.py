"""Admin endpoints — feature flags and user list (admin-only).

Public endpoint /jeli/admin/settings is unauthenticated so Pazuru/Tsumi can poll it.
"""

from __future__ import annotations

import logging
import sqlite3

import httpx
from fastapi import APIRouter, Cookie, Depends, Form, HTTPException, Response, UploadFile, status
from pydantic import BaseModel, ValidationError

import backup_orchestrator
import backup_service
import invite_codes as invite_codes_gen
from auth import repository as repo
from auth.conn import get_conn
from auth.dependencies import require_admin
from auth.models import AdminKpis, InviteCode, InviteCodeCreateRequest, UserPublic
from config import settings
from settings_store import DEFAULT_SETTINGS, get_all, set_value

router = APIRouter(tags=["admin"])
logger = logging.getLogger(__name__)


def _invalidate_downstream_settings_caches() -> None:
    """Best-effort notify Pazuru/Tsumi to drop their cached settings snapshot
    right after a write here, so a rapid toggle+restore doesn't leave either
    app serving a stale value for up to their SettingsCache TTL (300s).
    Confirmed live 2026-09-17: this staleness caused a false 402 on Tsumi's
    require_feature() shortly after a premium_gating_enabled toggle+restore.
    Never raises -- same resilience posture as the polling endpoint this
    mirrors (public_get_settings below). Sends the shared X-Internal-Token
    (foroba#299) and is skipped with a warning when INTERNAL_API_TOKEN is unset."""
    token = settings.internal_api_token
    if not token:
        logger.warning("INTERNAL_API_TOKEN unset; skipping settings-cache invalidate push")
        return
    for base in (settings.pazuru_api_url, settings.tsumi_api_url):
        url = f"{base.rstrip('/')}/jeli/settings-cache/invalidate"
        try:
            httpx.post(url, headers={"X-Internal-Token": token}, timeout=2)
        except httpx.HTTPError as exc:
            logger.warning("settings-cache invalidate failed for %s: %s", url, exc)


class SettingPatch(BaseModel):
    value: str


class BackupExportRequest(BaseModel):
    passphrase: str


@router.get("/admin/settings")
def admin_get_settings(
    conn: sqlite3.Connection = Depends(get_conn),
    _: dict = Depends(require_admin),
) -> dict[str, str]:
    return get_all(conn)


@router.patch("/admin/settings/{key}")
def admin_patch_setting(
    key: str,
    body: SettingPatch,
    conn: sqlite3.Connection = Depends(get_conn),
    _: dict = Depends(require_admin),
) -> dict[str, str]:
    if key not in DEFAULT_SETTINGS:
        raise HTTPException(status.HTTP_404_NOT_FOUND, f"Unknown key: {key!r}")
    if body.value not in ("true", "false"):
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, "value must be 'true' or 'false'")
    set_value(conn, key, body.value)
    _invalidate_downstream_settings_caches()
    return get_all(conn)


@router.get("/admin/users", response_model=list[UserPublic])
def admin_get_users(
    conn: sqlite3.Connection = Depends(get_conn),
    _: dict = Depends(require_admin),
) -> list[dict]:
    """Validate rows individually rather than relying solely on FastAPI's
    list[UserPublic] response-model validation (FOR-D05): one malformed
    legacy row (e.g. an out-of-band insert with a reserved-TLD email) must
    not 500 the entire list. Any row that still fails is logged and skipped."""
    users = []
    for row in repo.list_all_users(conn):
        try:
            users.append(UserPublic(**row).model_dump())
        except ValidationError:
            logger.warning("Skipping malformed user row id=%r in /admin/users", row.get("id"))
    return users


class AccountDisabledPatch(BaseModel):
    disabled: bool


@router.patch("/admin/users/{user_id}/disabled", response_model=UserPublic)
def admin_set_account_disabled(
    user_id: int,
    body: AccountDisabledPatch,
    conn: sqlite3.Connection = Depends(get_conn),
    admin: dict = Depends(require_admin),
) -> dict:
    if user_id == admin["id"]:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Cannot disable your own account")
    target = repo.get_user_by_id(conn, user_id)
    if target is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "User not found")
    repo.set_account_disabled(conn, user_id, body.disabled)
    return repo.get_user_by_id(conn, user_id)


@router.get("/jeli/admin/settings")
def public_get_settings(conn: sqlite3.Connection = Depends(get_conn)) -> dict[str, str]:
    """Unauthenticated read — for Pazuru/Tsumi SettingsCache polling, and so
    RegisterPage can check `require_invite_code` before rendering that field."""
    return get_all(conn)


@router.get("/admin/kpis", response_model=AdminKpis)
def admin_get_kpis(
    conn: sqlite3.Connection = Depends(get_conn),
    _: dict = Depends(require_admin),
) -> dict:
    return repo.get_admin_kpis(conn)


@router.get("/admin/invite-codes", response_model=list[InviteCode])
def admin_list_invite_codes(
    conn: sqlite3.Connection = Depends(get_conn),
    _: dict = Depends(require_admin),
) -> list[dict]:
    return repo.list_invite_codes(conn)


@router.post("/admin/invite-codes", response_model=InviteCode, status_code=201)
def admin_create_invite_code(
    body: InviteCodeCreateRequest,
    conn: sqlite3.Connection = Depends(get_conn),
    admin: dict = Depends(require_admin),
) -> dict:
    return repo.create_invite_code(
        conn,
        code=invite_codes_gen.generate_code(),
        note=body.note,
        max_uses=body.max_uses,
        expires_at=body.expires_at,
        created_by_user_id=admin["id"],
    )


@router.delete("/admin/invite-codes/{code_id}", status_code=204)
def admin_revoke_invite_code(
    code_id: int,
    conn: sqlite3.Connection = Depends(get_conn),
    _: dict = Depends(require_admin),
) -> None:
    if not repo.revoke_invite_code(conn, code_id):
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Invite code not found or already revoked")


@router.get("/admin/backup/export")
def admin_export_backup(_: dict = Depends(require_admin)) -> Response:
    data = backup_service.export_archive()
    return Response(content=data, media_type="application/gzip")


@router.post("/admin/backup/import")
async def admin_import_backup(file: UploadFile, _: dict = Depends(require_admin)) -> dict:
    data = await file.read()
    try:
        return backup_service.import_archive(data)
    except (ValueError, OSError) as exc:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, str(exc)) from exc


@router.post("/admin/backup/export-suite")
async def admin_export_suite(
    body: BackupExportRequest,
    _: dict = Depends(require_admin),
    suite_session: str | None = Cookie(default=None),
    stepup_pazuru: str | None = Cookie(default=None),
    stepup_tsumi: str | None = Cookie(default=None),
) -> Response:
    stepup = {k: v for k, v in (("pazuru", stepup_pazuru), ("tsumi", stepup_tsumi)) if v}
    data = await backup_orchestrator.export_suite(
        body.passphrase, cookie=suite_session, stepup=stepup
    )
    return Response(content=data, media_type="application/octet-stream")


@router.post("/admin/backup/import-suite")
async def admin_import_suite(
    file: UploadFile,
    passphrase: str = Form(...),
    _: dict = Depends(require_admin),
    suite_session: str | None = Cookie(default=None),
    stepup_pazuru: str | None = Cookie(default=None),
    stepup_tsumi: str | None = Cookie(default=None),
) -> dict:
    data = await file.read()
    stepup = {k: v for k, v in (("pazuru", stepup_pazuru), ("tsumi", stepup_tsumi)) if v}
    try:
        return await backup_orchestrator.import_suite(
            data, passphrase, cookie=suite_session, stepup=stepup
        )
    except (backup_orchestrator.InvalidPassphrase, ValueError) as exc:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, str(exc)) from exc
