"""Webhook registration & management endpoints (foroba#165, TI-D item 5, Plan A)."""

from __future__ import annotations

import secrets
import sqlite3

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, field_validator

import db
from auth.conn import get_conn
from auth.dependencies import get_current_user

router = APIRouter(prefix="/auth/webhooks", tags=["webhooks"])


class WebhookCreate(BaseModel):
    target_url: str

    @field_validator("target_url")
    @classmethod
    def _require_https(cls, v: str) -> str:
        if not v.startswith("https://"):
            raise ValueError("target_url must use https://")
        return v


class WebhookOut(BaseModel):
    id: int
    target_url: str
    is_active: bool
    consecutive_failures: int
    disabled_at: str | None
    created_at: str


class WebhookCreated(WebhookOut):
    signing_secret: str  # shown once, never re-displayed after creation


def _to_out(row: sqlite3.Row) -> WebhookOut:
    return WebhookOut(
        id=row["id"],
        target_url=row["target_url"],
        is_active=bool(row["is_active"]),
        consecutive_failures=row["consecutive_failures"],
        disabled_at=row["disabled_at"],
        created_at=row["created_at"],
    )


@router.post("", response_model=WebhookCreated, status_code=201)
def create_webhook(
    body: WebhookCreate,
    user: dict = Depends(get_current_user),
    conn: sqlite3.Connection = Depends(get_conn),
) -> WebhookCreated:
    signing_secret = secrets.token_urlsafe(32)
    row = db.create_webhook(
        conn, user_id=user["id"], target_url=body.target_url, signing_secret=signing_secret
    )
    return WebhookCreated(**_to_out(row).model_dump(), signing_secret=signing_secret)


@router.get("", response_model=list[WebhookOut])
def list_webhooks(
    user: dict = Depends(get_current_user),
    conn: sqlite3.Connection = Depends(get_conn),
) -> list[WebhookOut]:
    return [_to_out(r) for r in db.list_webhooks(conn, user_id=user["id"])]


@router.delete("/{webhook_id}", status_code=204)
def delete_webhook(
    webhook_id: int,
    user: dict = Depends(get_current_user),
    conn: sqlite3.Connection = Depends(get_conn),
) -> None:
    if not db.delete_webhook(conn, webhook_id, user_id=user["id"]):
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Webhook not found")


@router.post("/{webhook_id}/reactivate", response_model=WebhookOut)
def reactivate_webhook(
    webhook_id: int,
    user: dict = Depends(get_current_user),
    conn: sqlite3.Connection = Depends(get_conn),
) -> WebhookOut:
    row = db.reactivate_webhook(conn, webhook_id, user_id=user["id"])
    if row is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Webhook not found")
    return _to_out(row)
