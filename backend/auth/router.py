"""Auth endpoints: register, login, logout, me."""

from __future__ import annotations

import sqlite3
import uuid

from fastapi import APIRouter, Depends, File, HTTPException, Request, Response, UploadFile, status
from pydantic import BaseModel

from auth import keys
from auth import repository as repo
from auth.avatar_storage import save_avatar
from auth.conn import get_conn  # re-exported for tests that import it from here
from auth.dependencies import get_current_user
from auth.models import (
    ConsentRecord,
    DisplayCurrencyRequest,
    EmailOtpSendRequest,
    HouseholdJoinRequest,
    Login2FARequest,
    LoginRequest,
    NameUpdateRequest,
    RecoveryCodeLoginRequest,
    RegisterRequest,
    ShareToggleRequest,
    ShowDebtsRequest,
    UserPublic,
)
from auth.security import create_token, hash_password, needs_rehash, verify_password
from config import settings
from email_otp import EmailNotConfiguredError, generate_and_send
from email_otp import verify_and_consume as verify_email_otp
from legal import PRIVACY_VERSION, TOS_VERSION
from passkeys.service import authentication_options_for_user
from passkeys.service import verify_authentication as verify_webauthn_authentication
from rate_limit import limiter
from recovery_codes import verify_and_consume as verify_recovery_code
from twofa.totp import verify_code

router = APIRouter(prefix="/auth", tags=["auth"])


def _set_session_cookie(response: Response, user: dict) -> None:
    private_key, _, kid = keys.get_keypair(settings)
    token = create_token(
        user["id"],
        private_key,
        settings.jwt_ttl_minutes,
        tier=user.get("tier", "free"),
        audience=user.get("audience", "base"),
        is_admin=bool(user.get("is_admin", 0)),
        kid=kid,
    )
    response.set_cookie(
        "suite_session",
        token,
        httponly=True,
        samesite="lax",
        secure=settings.cookie_secure,
        max_age=settings.jwt_ttl_minutes * 60,
        domain=settings.cookie_domain or None,
    )


@router.post("/register", response_model=UserPublic, status_code=201)
@limiter.limit("5/minute")
def register(
    request: Request,
    req: RegisterRequest,
    response: Response,
    conn: sqlite3.Connection = Depends(get_conn),
) -> dict:
    if repo.get_user_by_email(conn, req.email):
        raise HTTPException(status.HTTP_409_CONFLICT, "Email already registered")
    user = repo.create_user(
        conn,
        email=req.email,
        name=req.name,
        password_hash=hash_password(req.password),
        birth_year=req.birth_year,
        country=req.country,
    )
    client_ip = request.client.host if request.client else None
    repo.record_consent(
        conn,
        user_id=user["id"],
        document_type="terms_of_service",
        document_version=TOS_VERSION,
        ip_address=client_ip,
    )
    repo.record_consent(
        conn,
        user_id=user["id"],
        document_type="privacy_policy",
        document_version=PRIVACY_VERSION,
        ip_address=client_ip,
    )
    _set_session_cookie(response, user)
    return user


@router.get("/consents", response_model=list[ConsentRecord])
def get_consents(
    user: dict = Depends(get_current_user), conn: sqlite3.Connection = Depends(get_conn)
) -> list[dict]:
    return repo.get_consents(conn, user["id"])


@router.post("/onboarding/complete", status_code=204)
def complete_onboarding(
    user: dict = Depends(get_current_user), conn: sqlite3.Connection = Depends(get_conn)
) -> None:
    repo.complete_onboarding(conn, user["id"])


@router.post("/login", response_model=None)
@limiter.limit("10/minute")
def login(
    request: Request,
    req: LoginRequest,
    response: Response,
    conn: sqlite3.Connection = Depends(get_conn),
) -> dict:
    user = repo.get_user_by_email(conn, req.email)
    if user is not None and repo.is_locked_out(user):
        raise HTTPException(status.HTTP_423_LOCKED, "Account temporarily locked. Try again later.")
    if user is not None and user.get("account_disabled"):
        raise HTTPException(status.HTTP_403_FORBIDDEN, "This account has been disabled.")
    if user is None or not verify_password(req.password, user["password_hash"]):
        if user is not None:
            repo.register_failed_login(conn, user["id"])
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Invalid credentials")
    if needs_rehash(user["password_hash"]):
        new_hash = hash_password(req.password)
        conn.execute("UPDATE users SET password_hash = ? WHERE id = ?", (new_hash, user["id"]))
        conn.commit()
    if _has_any_mfa_method(user) and settings.auth_2fa_enabled:
        return {"mfa_required": True, "email": user["email"], "methods": _enabled_methods(user)}
    repo.reset_failed_login(conn, user["id"])
    _set_session_cookie(response, user)
    return UserPublic(**user).model_dump()


@router.post("/login/2fa", response_model=None)
@limiter.limit("10/minute")
def login_2fa(
    request: Request,
    req: Login2FARequest,
    response: Response,
    conn: sqlite3.Connection = Depends(get_conn),
) -> dict:
    user = repo.get_user_by_email(conn, req.email)
    if user is not None and repo.is_locked_out(user):
        raise HTTPException(status.HTTP_423_LOCKED, "Account temporarily locked. Try again later.")
    if user is not None and user.get("account_disabled"):
        raise HTTPException(status.HTTP_403_FORBIDDEN, "This account has been disabled.")
    if user is None:
        raise HTTPException(400, "2FA not set up")
    if req.method == "totp":
        totp_ok = (
            user.get("totp_enabled")
            and user.get("totp_secret")
            and verify_code(user["totp_secret"], req.code)
        )
        if not totp_ok:
            repo.register_failed_login(conn, user["id"])
            raise HTTPException(401, "Invalid code")
    elif req.method == "email_otp":
        if not user.get("email_otp_enabled") or not verify_email_otp(conn, user["id"], req.code):
            repo.register_failed_login(conn, user["id"])
            raise HTTPException(401, "Invalid code")
    repo.reset_failed_login(conn, user["id"])
    _set_session_cookie(response, user)
    return UserPublic(**user).model_dump()


@router.post("/login/email-otp/send")
@limiter.limit("5/minute")
def login_email_otp_send(
    request: Request,
    req: EmailOtpSendRequest,
    conn: sqlite3.Connection = Depends(get_conn),
) -> dict:
    """Pre-auth email-OTP send for the login-challenge step. Unlike /auth/2fa/email-otp/send
    (which is for enrollment/step-up and reads the authenticated user from the session), this
    endpoint runs before a session exists — the login-challenge screen has no cookie yet — so it
    takes `email` in the body and looks the user up directly. Rate-limited like the rest of the
    login surface to prevent using it as an email-flooding vector."""
    user = repo.get_user_by_email(conn, req.email)
    if user is None or not user.get("email_otp_enabled"):
        raise HTTPException(400, "Email OTP is not set up for this account")
    if repo.is_locked_out(user):
        raise HTTPException(status.HTTP_423_LOCKED, "Account temporarily locked. Try again later.")
    try:
        generate_and_send(conn, user["id"], user["email"])
    except EmailNotConfiguredError as exc:
        raise HTTPException(503, "Email delivery is not configured") from exc
    return {"sent": True}


@router.post("/login/recovery-code", response_model=None)
@limiter.limit("5/minute")
def login_recovery_code(
    request: Request,
    req: RecoveryCodeLoginRequest,
    response: Response,
    conn: sqlite3.Connection = Depends(get_conn),
) -> dict:
    user = repo.get_user_by_email(conn, req.email)
    if user is not None and repo.is_locked_out(user):
        raise HTTPException(status.HTTP_423_LOCKED, "Account temporarily locked. Try again later.")
    if user is not None and user.get("account_disabled"):
        raise HTTPException(status.HTTP_403_FORBIDDEN, "This account has been disabled.")
    if user is None or not verify_recovery_code(conn, user["id"], req.recovery_code):
        if user is not None:
            repo.register_failed_login(conn, user["id"])
        raise HTTPException(401, "Invalid recovery code")
    repo.reset_failed_login(conn, user["id"])
    _set_session_cookie(response, user)
    return UserPublic(**user).model_dump()


class WebauthnLoginOptionsRequest(BaseModel):
    email: str


@router.post("/login/webauthn/options-by-email")
@limiter.limit("10/minute")
def login_webauthn_options_by_email(
    request: Request,
    req: WebauthnLoginOptionsRequest,
    conn: sqlite3.Connection = Depends(get_conn),
) -> dict:
    import json

    user = repo.get_user_by_email(conn, req.email)
    if user is None or not user.get("webauthn_enabled"):
        raise HTTPException(400, "Passkey not set up for this account")
    return json.loads(authentication_options_for_user(conn, user["id"]))


class WebauthnLoginVerifyRequest(BaseModel):
    email: str
    credential: str


@router.post("/login/webauthn/verify", response_model=None)
@limiter.limit("10/minute")
def login_webauthn_verify(
    request: Request,
    req: WebauthnLoginVerifyRequest,
    response: Response,
    conn: sqlite3.Connection = Depends(get_conn),
) -> dict:
    user = repo.get_user_by_email(conn, req.email)
    if user is None or not user.get("webauthn_enabled"):
        raise HTTPException(401, "Passkey not set up for this account")
    if not verify_webauthn_authentication(conn, user["id"], req.credential):
        raise HTTPException(401, "Passkey verification failed")
    repo.reset_failed_login(conn, user["id"])
    _set_session_cookie(response, user)
    return UserPublic(**user).model_dump()


def _has_any_mfa_method(user: dict) -> bool:
    return bool(
        user.get("totp_enabled") or user.get("email_otp_enabled") or user.get("webauthn_enabled")
    )


def _enabled_methods(user: dict) -> list[str]:
    methods = []
    if user.get("totp_enabled"):
        methods.append("totp")
    if user.get("email_otp_enabled"):
        methods.append("email_otp")
    if user.get("webauthn_enabled"):
        methods.append("webauthn")
    return methods


@router.post("/logout", status_code=204)
def logout(response: Response) -> None:
    response.delete_cookie("suite_session")


@router.get("/me", response_model=UserPublic)
def me(user: dict = Depends(get_current_user)) -> dict:
    return user


@router.get("/household")
def get_household(
    user: dict = Depends(get_current_user), conn: sqlite3.Connection = Depends(get_conn)
) -> dict:
    household_id = user.get("household_id")
    members = repo.get_household_members(conn, household_id) if household_id else []
    return {
        "household_id": household_id,
        "members": members,
        "share_preferences": repo.get_share_preferences(conn, user["id"]),
    }


@router.post("/household/join")
def join_household(
    req: HouseholdJoinRequest,
    user: dict = Depends(get_current_user),
    conn: sqlite3.Connection = Depends(get_conn),
) -> dict:
    if req.email == user["email"]:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Cannot join a household with yourself")
    other = repo.get_user_by_email(conn, req.email)
    if other is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "No user with that email")
    household_id = user.get("household_id") or other.get("household_id") or str(uuid.uuid4())
    repo.set_household_id(conn, user["id"], household_id)
    repo.set_household_id(conn, other["id"], household_id)
    return {
        "household_id": household_id,
        "members": repo.get_household_members(conn, household_id),
    }


@router.post("/household/leave", status_code=204)
def leave_household(
    user: dict = Depends(get_current_user), conn: sqlite3.Connection = Depends(get_conn)
) -> None:
    repo.set_household_id(conn, user["id"], None)


@router.put("/household/share", status_code=204)
def set_share_preference(
    req: ShareToggleRequest,
    user: dict = Depends(get_current_user),
    conn: sqlite3.Connection = Depends(get_conn),
) -> None:
    repo.set_share_preference(conn, user["id"], req.resource_type, req.shared)


@router.put("/me/currency", status_code=204)
def set_display_currency(
    req: DisplayCurrencyRequest,
    user: dict = Depends(get_current_user),
    conn: sqlite3.Connection = Depends(get_conn),
) -> None:
    repo.set_display_currency(conn, user["id"], req.display_currency.upper())


@router.put("/me/show-debts", status_code=204)
def update_show_debts(
    req: ShowDebtsRequest,
    user: dict = Depends(get_current_user),
    conn: sqlite3.Connection = Depends(get_conn),
) -> None:
    repo.set_show_debts(conn, user["id"], req.show_debts)


@router.put("/me/name", status_code=204)
def update_name(
    req: NameUpdateRequest,
    user: dict = Depends(get_current_user),
    conn: sqlite3.Connection = Depends(get_conn),
) -> None:
    repo.set_name(conn, user["id"], req.first_name, req.last_name)


@router.post("/me/avatar")
async def upload_avatar(
    file: UploadFile = File(...),
    user: dict = Depends(get_current_user),
    conn: sqlite3.Connection = Depends(get_conn),
) -> dict:
    content = await file.read()
    avatar_url = save_avatar(user["id"], file, content)
    repo.set_avatar_url(conn, user["id"], avatar_url)
    return {"avatar_url": avatar_url}


@router.get("/visible-owners")
def visible_owners(
    resource_type: str,
    user: dict = Depends(get_current_user),
    conn: sqlite3.Connection = Depends(get_conn),
) -> dict:
    return {"owner_ids": repo.get_visible_owner_ids(conn, user["id"], resource_type)}
