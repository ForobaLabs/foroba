"""Admin endpoints — feature flags and user list (admin-only).

Public endpoint /jeli/admin/settings is unauthenticated so Pazuru/Tsumi can poll it.
"""
from __future__ import annotations

import sqlite3

from fastapi import APIRouter, Cookie, Depends, Form, HTTPException, Response, UploadFile, status
from pydantic import BaseModel

import backup_orchestrator
import backup_service
from auth.conn import get_conn
from auth.dependencies import get_current_user, require_admin
from auth import repository as repo
from auth.models import UserPublic
from settings_store import DEFAULT_SETTINGS, get_all, set_value

router = APIRouter(tags=["admin"])


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
    return get_all(conn)


@router.get("/admin/users", response_model=list[UserPublic])
def admin_get_users(
    conn: sqlite3.Connection = Depends(get_conn),
    _: dict = Depends(require_admin),
) -> list[dict]:
    return repo.list_all_users(conn)


@router.get("/jeli/admin/settings")
def public_get_settings(conn: sqlite3.Connection = Depends(get_conn)) -> dict[str, str]:
    """Unauthenticated read — for Pazuru/Tsumi SettingsCache polling."""
    return get_all(conn)


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
        raise HTTPException(status.HTTP_400_BAD_REQUEST, str(exc))


@router.post("/admin/backup/export-suite")
async def admin_export_suite(
    body: BackupExportRequest,
    _: dict = Depends(require_admin),
    suite_session: str | None = Cookie(default=None),
) -> Response:
    data = await backup_orchestrator.export_suite(body.passphrase, cookie=suite_session)
    return Response(content=data, media_type="application/octet-stream")


@router.post("/admin/backup/import-suite")
async def admin_import_suite(
    file: UploadFile,
    passphrase: str = Form(...),
    _: dict = Depends(require_admin),
    suite_session: str | None = Cookie(default=None),
) -> dict:
    data = await file.read()
    try:
        return await backup_orchestrator.import_suite(data, passphrase, cookie=suite_session)
    except (backup_orchestrator.InvalidPassphrase, ValueError) as exc:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, str(exc))
