"""Auth endpoints: register, login, logout, me."""
from __future__ import annotations

import sqlite3

from fastapi import APIRouter, Depends, HTTPException, Response, status
from pydantic import BaseModel

from config import settings
from auth.conn import get_conn  # re-exported for tests that import it from here
from auth import repository as repo
from auth.dependencies import get_current_user
from auth.models import LoginRequest, RegisterRequest, UserPublic
from auth.security import create_token, hash_password, needs_rehash, verify_password
from twofa.totp import verify_code

router = APIRouter(prefix="/auth", tags=["auth"])


def _set_session_cookie(response: Response, user: dict) -> None:
    token = create_token(
        user["id"], settings.suite_jwt_secret, settings.jwt_ttl_minutes,
        tier=user.get("tier", "free"),
        audience=user.get("audience", "base"),
        is_admin=bool(user.get("is_admin", 0)),
    )
    response.set_cookie(
        "suite_session", token, httponly=True, samesite="lax",
        secure=settings.cookie_secure, max_age=settings.jwt_ttl_minutes * 60,
    )


@router.post("/register", response_model=UserPublic, status_code=201)
def register(req: RegisterRequest, response: Response,
             conn: sqlite3.Connection = Depends(get_conn)) -> dict:
    if repo.get_user_by_email(conn, req.email):
        raise HTTPException(status.HTTP_409_CONFLICT, "Email already registered")
    user = repo.create_user(conn, email=req.email, name=req.name,
                            password_hash=hash_password(req.password))
    _set_session_cookie(response, user)
    return user


@router.post("/login", response_model=None)
def login(req: LoginRequest, response: Response,
          conn: sqlite3.Connection = Depends(get_conn)) -> dict:
    user = repo.get_user_by_email(conn, req.email)
    if user is None or not verify_password(req.password, user["password_hash"]):
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Invalid credentials")
    if needs_rehash(user["password_hash"]):
        new_hash = hash_password(req.password)
        conn.execute("UPDATE users SET password_hash = ? WHERE id = ?", (new_hash, user["id"]))
        conn.commit()
    if settings.auth_2fa_enabled and user.get("totp_enabled"):
        return {"mfa_required": True, "email": user["email"]}
    _set_session_cookie(response, user)
    return UserPublic(**user).model_dump()


class Login2FARequest(BaseModel):
    email: str
    code: str


@router.post("/login/2fa", response_model=None)
def login_2fa(req: Login2FARequest, response: Response,
              conn: sqlite3.Connection = Depends(get_conn)) -> dict:
    user = repo.get_user_by_email(conn, req.email)
    if user is None or not user.get("totp_enabled") or not user.get("totp_secret"):
        raise HTTPException(400, "2FA not set up")
    if not verify_code(user["totp_secret"], req.code):
        raise HTTPException(401, "Invalid code")
    _set_session_cookie(response, user)
    return UserPublic(**user).model_dump()


@router.post("/logout", status_code=204)
def logout(response: Response) -> None:
    response.delete_cookie("suite_session")


@router.get("/me", response_model=UserPublic)
def me(user: dict = Depends(get_current_user)) -> dict:
    return user
