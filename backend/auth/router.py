"""Auth endpoints: register, login, logout, me."""

from __future__ import annotations

import asyncio
import hashlib
import secrets
import sqlite3
import uuid
from datetime import UTC, datetime, timedelta

import httpx
from argon2 import PasswordHasher as _PasswordHasher
from fastapi import (
    APIRouter,
    Cookie,
    Depends,
    File,
    Header,
    HTTPException,
    Request,
    Response,
    UploadFile,
    status,
)
from pydantic import BaseModel

import security_log
from auth import keys, refresh_tokens
from auth import repository as repo
from auth.avatar_storage import save_avatar
from auth.conn import get_conn  # re-exported for tests that import it from here
from auth.dependencies import _token_from_header, get_current_user
from auth.models import (
    ChangePasswordRequest,
    ConsentRecord,
    DeleteAccountRequest,
    DisplayCurrencyRequest,
    EmailChangeConfirmRequest,
    EmailChangeRequestModel,
    EmailOtpSendRequest,
    EmailVerifyRequest,
    HouseholdInviteAcceptRequest,
    HouseholdInviteRequest,
    HouseholdJoinRequest,
    Login2FARequest,
    LoginRequest,
    NameUpdateRequest,
    PasswordResetConfirmRequest,
    PasswordResetRequestModel,
    RecoveryCodeLoginRequest,
    RegisterRequest,
    ShareToggleRequest,
    ShowDebtsRequest,
    UserPublic,
)
from auth.security import check_password, create_token, hash_password, needs_rehash, verify_password
from auth.session_invalidation import invalidate_sessions_downstream
from billing.provider import BillingProviderError, get_provider
from config import settings
from email_otp import EmailNotConfiguredError, generate_and_send, generate_and_send_signup_verify
from email_otp import verify_and_consume as verify_email_otp
from email_service import send_email_change_email, send_household_invite_email
from legal import PRIVACY_VERSION, TOS_VERSION
from passkeys.service import authentication_options_for_user
from passkeys.service import verify_authentication as verify_webauthn_authentication
from rate_limit import limiter
from recovery_codes import verify_and_consume as verify_recovery_code
from settings_store import get_all as get_settings
from stepup import issue_stepup_cookies
from suite_cookies import suite_cookies
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
        session_version=user.get("session_version", 1),
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
    # GL-10.1 (foroba#185): invite-only gating is opt-in via the require_invite_code
    # runtime setting, off by default — self-host deployments keep open registration.
    if get_settings(conn).get("require_invite_code") == "true":
        if not req.invite_code or not repo.redeem_invite_code(conn, req.invite_code):
            raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, "Invalid invite code")
    # A2 (foroba#178): new users start unverified when SMTP is configured.
    # If SMTP is disabled (self-host without email), mark them as verified immediately.
    send_verify = settings.smtp_enabled
    user = repo.create_user(
        conn,
        email=req.email,
        name=req.name,
        password_hash=hash_password(req.password),
        birth_year=req.birth_year,
        country=req.country,
        require_mfa_enrollment=True,
        email_verified=not send_verify,
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
    if send_verify:
        try:
            generate_and_send_signup_verify(conn, user["id"], user["email"], country=req.country)
        except Exception:
            pass  # non-blocking — user can resend; don't fail registration
    _set_session_cookie(response, user)
    return user


@router.get("/consents", response_model=list[ConsentRecord])
def get_consents(
    user: dict = Depends(get_current_user), conn: sqlite3.Connection = Depends(get_conn)
) -> list[dict]:
    return repo.get_consents(conn, user["id"])


# CL-2.1 — re-consent enforcement
_REQUIRED_DOCS = {
    "terms_of_service": lambda: TOS_VERSION,
    "privacy_policy": lambda: PRIVACY_VERSION,
}


class ConsentAcceptRequest(BaseModel):
    documents: list[str]


@router.get("/consents/status")
def consents_status(
    user: dict = Depends(get_current_user), conn: sqlite3.Connection = Depends(get_conn)
) -> dict[str, bool]:
    """Return whether each required document has been accepted at its current version."""
    latest = repo.latest_consent_versions(conn, user["id"])
    return {doc: latest.get(doc) == current() for doc, current in _REQUIRED_DOCS.items()}


@router.post("/consents/accept", status_code=204)
def consents_accept(
    body: ConsentAcceptRequest,
    request: Request,
    user: dict = Depends(get_current_user),
    conn: sqlite3.Connection = Depends(get_conn),
) -> None:
    """Record new consent for one or more legal documents at their current version."""
    ip = request.client.host if request.client else None
    documents = list(dict.fromkeys(body.documents))  # idempotent: dedupe within the request
    for doc in documents:
        if doc not in _REQUIRED_DOCS:
            raise HTTPException(status_code=400, detail=f"unknown document: {doc}")
    for doc in documents:
        repo.record_consent(
            conn,
            user_id=user["id"],
            document_type=doc,
            document_version=_REQUIRED_DOCS[doc](),
            ip_address=ip,
        )
    conn.commit()


@router.post("/onboarding/complete", status_code=204)
def complete_onboarding(
    user: dict = Depends(get_current_user), conn: sqlite3.Connection = Depends(get_conn)
) -> None:
    repo.complete_onboarding(conn, user["id"])


# CL-2.2 — DSAR: processing preferences + portability export


class ProcessingPrefs(BaseModel):
    processing_restricted: bool | None = None
    marketing_objection: bool | None = None


@router.put("/me/processing", status_code=204)
def update_processing(
    body: ProcessingPrefs,
    user: dict = Depends(get_current_user),
    conn: sqlite3.Connection = Depends(get_conn),
) -> None:
    """GDPR art.18/21 — set processing-restriction and/or marketing-objection flags."""
    repo.update_processing_prefs(
        conn,
        user["id"],
        processing_restricted=body.processing_restricted,
        marketing_objection=body.marketing_objection,
    )
    conn.commit()


@router.get("/account/export")
async def export_account(
    user: dict = Depends(get_current_user),
    conn: sqlite3.Connection = Depends(get_conn),
    suite_session: str | None = Cookie(default=None),
) -> dict:
    """GDPR art.20 — machine-readable portability bundle: Foroba + Pazuru + Tsumi data."""
    profile = dict(user)
    profile.pop("password_hash", None)
    consents = repo.get_consents(conn, user["id"])

    stepup = issue_stepup_cookies(user["id"])
    cookies = suite_cookies(
        suite_session, stepup_pazuru=stepup["pazuru"], stepup_tsumi=stepup["tsumi"]
    )

    async def _get_app_data(url: str) -> dict:
        try:
            async with httpx.AsyncClient(timeout=10.0) as c:
                r = await c.get(url, cookies=cookies)
                if r.status_code == 200:
                    return r.json()
        except httpx.HTTPError:
            pass
        return {}

    pazuru_data = await _get_app_data(f"{settings.pazuru_api_url.rstrip('/')}/account/export")
    tsumi_data = await _get_app_data(f"{settings.tsumi_api_url.rstrip('/')}/account/export")

    subscriptions = [
        dict(row)
        for row in conn.execute(
            "SELECT provider, provider_subscription_id, provider_customer_id, status, "
            "current_period_end, cancel_at_period_end, last_event_at FROM subscriptions "
            "WHERE user_id = ?",
            (user["id"],),
        ).fetchall()
    ]

    return {
        "foroba": {"profile": profile, "consents": consents, "subscriptions": subscriptions},
        "pazuru": pazuru_data,
        "tsumi": tsumi_data,
    }


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
    if not check_password(req.password, user):
        if user is not None:
            repo.register_failed_login(conn, user["id"])
        _ip = request.client.host if request.client else None
        _uid = user["id"] if user is not None else None
        security_log.log_event(conn, user_id=_uid, event="login_failed",
                               detail="invalid credentials", ip=_ip)
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Invalid credentials")
    if needs_rehash(user["password_hash"]):
        new_hash = hash_password(req.password)
        conn.execute("UPDATE users SET password_hash = ? WHERE id = ?", (new_hash, user["id"]))
        conn.commit()
    if _has_any_mfa_method(user) and settings.auth_2fa_enabled:
        return {"mfa_required": True, "email": user["email"], "methods": _enabled_methods(user)}
    repo.reset_failed_login(conn, user["id"])
    security_log.log_event(conn, user_id=user["id"], event="login_success",
                           detail=None, ip=request.client.host if request.client else None)
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
def logout(
    response: Response,
    conn: sqlite3.Connection = Depends(get_conn),
    authorization: str | None = Header(default=None),
    suite_session: str | None = Cookie(default=None),
) -> None:
    """Clear the session cookie. When a valid session can be identified (Bearer header or
    cookie), also revoke all refresh tokens so native clients are signed out too."""
    response.delete_cookie("suite_session")
    # Resolve user id from Bearer header (native) or cookie (web) — best-effort,
    # do not raise on invalid/missing credentials.
    import jwt

    from auth import keys as _keys

    token = None
    if authorization:
        scheme, _, cred = authorization.partition(" ")
        if scheme.lower() == "bearer":
            token = cred.strip() or None
    if token is None:
        token = suite_session
    if token:
        try:
            _, public_key, _ = _keys.get_keypair(settings)
            from auth.security import decode_token

            claims = decode_token(token, public_key)
            refresh_tokens.revoke_all_for_user(conn, int(claims["sub"]))
            # XAPP-D03: bump the local session_version floor (invalidates
            # every already-issued suite_session JWT for this user, closing
            # the replay window the refresh-token revocation above doesn't
            # cover) and best-effort push the new floor to Pazuru/Tsumi.
            new_version = repo.bump_session_version(conn, int(claims["sub"]))
            invalidate_sessions_downstream(int(claims["sub"]), new_version)
        except (jwt.PyJWTError, Exception):
            pass  # logout succeeds even if we can't identify the user


_LIVE_SUB_STATUSES = ("active", "trialing", "past_due")


def _cancel_live_subscriptions(conn: sqlite3.Connection, user_id: int) -> None:
    """Cancel every still-billing subscription before erasure (Apple 5.1.1(v) / GDPR Art. 17:
    a deleted user must never be charged again). Raises BillingProviderError on any failure."""
    rows = conn.execute(
        "SELECT provider_subscription_id FROM subscriptions WHERE user_id = ? "
        "AND provider = 'paddle' AND status IN (?, ?, ?)",
        (user_id, *_LIVE_SUB_STATUSES),
    ).fetchall()
    provider = get_provider(settings.billing_provider)
    for (sub_id,) in rows:
        provider.cancel_subscription(sub_id)


@router.delete("/account", status_code=204)
@limiter.limit("5/minute")
async def delete_account(
    request: Request,
    req: DeleteAccountRequest,
    response: Response,
    user: dict = Depends(get_current_user),
    conn: sqlite3.Connection = Depends(get_conn),
    suite_session: str | None = Cookie(default=None),
    authorization: str | None = Header(default=None),
) -> None:
    """foroba#183 — GDPR Art. 17 erasure, triggered by the user themselves. All-or-
    nothing across the 3 apps: aborts before touching Foroba's own tables if either
    Pazuru's or Tsumi's erasure call fails, so we never delete Foroba's copy while
    the other apps still hold the user's data.

    Mints stepup_pazuru/stepup_tsumi directly (stepup.issue_stepup_cookies, same
    pattern as foroba#215's background jobs/API-key callers) rather than forwarding
    the browser's own stepup_<app> cookies -- those are only set once the user has
    actually visited Pazuru/Tsumi and expire after a short TTL, so a user who never
    (or long ago) visited those apps would otherwise always fail this all-or-nothing
    erasure with a 428 forwarded as 502. The password re-verification just above is
    already a stronger proof of identity than a step-up cookie.

    Live Paddle subscriptions are cancelled first; a cancellation failure aborts before
    any app's data is touched."""
    if not verify_password(req.password, user["password_hash"]):
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Invalid password")

    try:
        await asyncio.to_thread(_cancel_live_subscriptions, conn, user["id"])
    except BillingProviderError as exc:
        raise HTTPException(
            status.HTTP_502_BAD_GATEWAY,
            "Could not cancel your subscription — nothing was deleted. Please try again.",
        ) from exc

    stepup = issue_stepup_cookies(user["id"])
    # Bearer-authenticated clients (the mobile app) hold no suite_session cookie, but the
    # downstream apps authenticate the erase call from that cookie, so forward the token.
    session_token = suite_session or _token_from_header(authorization)
    cookies = suite_cookies(
        session_token, stepup_pazuru=stepup["pazuru"], stepup_tsumi=stepup["tsumi"]
    )
    pazuru_base = settings.pazuru_api_url.rstrip("/")
    tsumi_base = settings.tsumi_api_url.rstrip("/")
    try:
        async with httpx.AsyncClient(timeout=15.0) as client:
            pazuru_resp = await client.delete(f"{pazuru_base}/account/erase", cookies=cookies)
            tsumi_resp = await client.delete(f"{tsumi_base}/account/erase", cookies=cookies)
    except httpx.HTTPError as exc:
        raise HTTPException(
            status.HTTP_502_BAD_GATEWAY, "Account deletion failed — please try again"
        ) from exc
    if pazuru_resp.status_code >= 300 or tsumi_resp.status_code >= 300:
        raise HTTPException(
            status.HTTP_502_BAD_GATEWAY, "Account deletion failed — please try again"
        )

    repo.delete_user(conn, user["id"])
    response.delete_cookie("suite_session")


@router.get("/me", response_model=UserPublic)
def me(user: dict = Depends(get_current_user)) -> dict:
    return user


# ── A2: Email verification (foroba#178) ──────────────────────────────────────

@router.post("/verify-email", status_code=204)
@limiter.limit("10/minute")
def verify_email(
    request: Request,
    req: EmailVerifyRequest,
    user: dict = Depends(get_current_user),
    conn: sqlite3.Connection = Depends(get_conn),
) -> None:
    """Verify the user's email address using the OTP sent at signup."""
    if user.get("email_verified"):
        return  # already verified — idempotent
    if not verify_email_otp(conn, user["id"], req.code):
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Invalid or expired code")
    repo.set_email_verified(conn, user["id"], True)


@router.post("/resend-verification", status_code=204)
@limiter.limit("3/minute")
def resend_verification(
    request: Request,
    user: dict = Depends(get_current_user),
    conn: sqlite3.Connection = Depends(get_conn),
) -> None:
    """Re-send the email verification OTP."""
    if user.get("email_verified"):
        return  # already verified
    try:
        generate_and_send_signup_verify(
            conn, user["id"], user["email"], country=user.get("country")
        )
    except EmailNotConfiguredError as exc:
        raise HTTPException(
            status.HTTP_503_SERVICE_UNAVAILABLE,
            "Email delivery is not configured on this server",
        ) from exc


# ── A6: Email change flow (foroba#182) ───────────────────────────────────────

@router.post("/me/email/change-request", status_code=204)
@limiter.limit("5/minute")
def email_change_request(
    request: Request,
    req: EmailChangeRequestModel,
    user: dict = Depends(get_current_user),
    conn: sqlite3.Connection = Depends(get_conn),
) -> None:
    """Initiate an email address change: send OTP to the new address."""
    if not user.get("email_verified", True):
        raise HTTPException(
            status.HTTP_403_FORBIDDEN,
            "Verify your current email address before changing it",
        )
    if repo.get_user_by_email(conn, req.new_email.lower()):
        raise HTTPException(status.HTTP_409_CONFLICT, "Email already in use")
    if not settings.smtp_enabled:
        raise HTTPException(
            status.HTTP_503_SERVICE_UNAVAILABLE,
            "Email delivery is not configured on this server",
        )
    repo.set_pending_email(conn, user["id"], req.new_email.lower())
    code = f"{secrets.randbelow(1_000_000):06d}"
    expires_at = (datetime.now(UTC) + timedelta(minutes=10)).isoformat()
    conn.execute(
        "INSERT INTO email_otp_codes (user_id, code_hash, expires_at) VALUES (?, ?, ?)",
        (user["id"], _PasswordHasher().hash(code), expires_at),
    )
    conn.commit()
    send_email_change_email(req.new_email, code, country=user.get("country"))


@router.post("/me/email/change-confirm", status_code=204)
@limiter.limit("5/minute")
def email_change_confirm(
    request: Request,
    req: EmailChangeConfirmRequest,
    user: dict = Depends(get_current_user),
    conn: sqlite3.Connection = Depends(get_conn),
) -> None:
    """Confirm the email change OTP and apply the new address."""
    pending = user.get("pending_email")
    if not pending:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "No pending email change")
    if not verify_email_otp(conn, user["id"], req.code):
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Invalid or expired code")
    repo.apply_pending_email(conn, user["id"])
    repo.set_email_verified(conn, user["id"], True)


# ── A4: Household invite by email (foroba#180) ───────────────────────────────

_INVITE_TTL_HOURS = 48
_INVITE_TOKEN_BYTES = 6  # 6 bytes → 12 hex chars, easy to type


def _make_invite_token() -> tuple[str, str]:
    """Return (plain_token, sha256_hex_hash)."""
    raw = secrets.token_hex(_INVITE_TOKEN_BYTES).upper()
    hashed = hashlib.sha256(raw.encode()).hexdigest()
    return raw, hashed


def _send_household_invite(invited_email: str, user: dict, conn: sqlite3.Connection) -> None:
    """Create a consent-requiring household invite and email it to invited_email.

    Shared by /household/invite (A4, foroba#180) and /household/join
    (FOR-D04) -- household membership merging is symmetric, so "invite this
    email to my household" and "let me join that email's household" both
    resolve to the same consent-requiring token: the invited party must
    still call /household/invite/accept before any merge happens.
    """
    if not settings.smtp_enabled:
        raise HTTPException(
            status.HTTP_503_SERVICE_UNAVAILABLE,
            "Email delivery is not configured on this server",
        )
    if invited_email.lower() == user["email"].lower():
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Cannot invite yourself")
    household_id = user.get("household_id") or str(uuid.uuid4())
    if not user.get("household_id"):
        repo.set_household_id(conn, user["id"], household_id)
    token, token_hash = _make_invite_token()
    expires_at = (datetime.now(UTC) + timedelta(hours=_INVITE_TTL_HOURS)).isoformat()
    repo.create_household_invite(
        conn,
        inviter_id=user["id"],
        household_id=household_id,
        invited_email=invited_email.lower(),
        token_hash=token_hash,
        expires_at=expires_at,
    )
    send_household_invite_email(
        invited_email,
        token,
        inviter_name=user.get("first_name") or user["name"],
        country=user.get("country"),
    )


@router.post("/household/invite", status_code=204)
@limiter.limit("10/minute")
def household_invite(
    request: Request,
    req: HouseholdInviteRequest,
    user: dict = Depends(get_current_user),
    conn: sqlite3.Connection = Depends(get_conn),
) -> None:
    """Send an email invite to join the current user's household (A4, foroba#180)."""
    _send_household_invite(req.email, user, conn)


@router.post("/household/invite/accept", status_code=204)
@limiter.limit("10/minute")
def household_invite_accept(
    request: Request,
    req: HouseholdInviteAcceptRequest,
    user: dict = Depends(get_current_user),
    conn: sqlite3.Connection = Depends(get_conn),
) -> None:
    """Accept a household invite token (A4, foroba#180)."""
    token_hash = hashlib.sha256(req.token.upper().encode()).hexdigest()
    invite = repo.get_household_invite_by_token_hash(conn, token_hash)
    if invite is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Invite not found")
    if invite["accepted_at"]:
        raise HTTPException(status.HTTP_409_CONFLICT, "Invite already accepted")
    if invite["expires_at"] < datetime.now(UTC).isoformat():
        raise HTTPException(status.HTTP_410_GONE, "Invite has expired")
    if invite["invited_email"] != user["email"].lower():
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Invite is for a different email address")
    repo.set_household_id(conn, user["id"], invite["household_id"])
    repo.accept_household_invite(conn, invite["id"])


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


@router.post("/household/join", status_code=204)
@limiter.limit("10/minute")
def join_household(
    request: Request,
    req: HouseholdJoinRequest,
    user: dict = Depends(get_current_user),
    conn: sqlite3.Connection = Depends(get_conn),
) -> None:
    """Request to join another user's household (FOR-D04).

    Previously merged household_id immediately with zero notification or
    consent from the target. Now delegates to the same consent-requiring
    invite/accept flow /household/invite uses -- the target must accept
    before any merge happens.
    """
    _send_household_invite(req.email, user, conn)


@router.post("/household/leave", status_code=204)
def leave_household(
    user: dict = Depends(get_current_user), conn: sqlite3.Connection = Depends(get_conn)
) -> None:
    repo.set_household_id(conn, user["id"], None)
    # FOR-D04: a sharing opt-in given to the household being left must not
    # silently carry over and apply to whichever household is joined next.
    repo.clear_share_preferences(conn, user["id"])


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


@router.put("/me/password", status_code=204)
@limiter.limit("5/minute")
def change_password(
    request: Request,
    req: ChangePasswordRequest,
    user: dict = Depends(get_current_user),
    conn: sqlite3.Connection = Depends(get_conn),
) -> None:
    """Change the authenticated user's password. Revokes all refresh tokens so that
    mobile sessions (which can live for 30 days) are invalidated immediately."""
    if not verify_password(req.current_password, user["password_hash"]):
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Current password is incorrect")
    conn.execute(
        "UPDATE users SET password_hash = ? WHERE id = ?",
        (hash_password(req.new_password), user["id"]),
    )
    conn.commit()
    refresh_tokens.revoke_all_for_user(conn, user["id"])


@router.post("/me/password/reset-request", status_code=204)
@limiter.limit("5/minute")
def password_reset_request(
    request: Request,
    req: PasswordResetRequestModel,
    conn: sqlite3.Connection = Depends(get_conn),
) -> None:
    """Initiate a password reset via email OTP. Always returns 204 — even if the
    email is not registered — to avoid leaking which addresses exist."""
    user = repo.get_user_by_email(conn, req.email)
    if user is None:
        return  # silent — no oracle
    try:
        generate_and_send(conn, user["id"], user["email"])
    except EmailNotConfiguredError as exc:
        raise HTTPException(
            status.HTTP_503_SERVICE_UNAVAILABLE,
            "Email delivery is not configured on this server",
        ) from exc


@router.post("/me/password/reset", status_code=204)
@limiter.limit("5/minute")
def password_reset_confirm(
    request: Request,
    req: PasswordResetConfirmRequest,
    conn: sqlite3.Connection = Depends(get_conn),
) -> None:
    """Complete a password reset: verify the OTP, update the hash, revoke all
    refresh tokens. Returns 400 on invalid / expired code."""
    user = repo.get_user_by_email(conn, req.email)
    if user is None or not verify_email_otp(conn, user["id"], req.code):
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Invalid or expired code")
    conn.execute(
        "UPDATE users SET password_hash = ? WHERE id = ?",
        (hash_password(req.new_password), user["id"]),
    )
    conn.commit()
    refresh_tokens.revoke_all_for_user(conn, user["id"])


@router.get("/visible-owners")
def visible_owners(
    resource_type: str,
    user: dict = Depends(get_current_user),
    conn: sqlite3.Connection = Depends(get_conn),
) -> dict:
    return {"owner_ids": repo.get_visible_owner_ids(conn, user["id"], resource_type)}


# ── Push notification device-token registration (#37 — IOS-4.4) ──────────────

class DevicePushTokenRequest(BaseModel):
    token: str
    platform: str  # 'ios' | 'android'


@router.post("/device/push-token", status_code=204)
def register_device_push_token(
    req: DevicePushTokenRequest,
    user: dict = Depends(get_current_user),
    conn: sqlite3.Connection = Depends(get_conn),
) -> None:
    """Store the APNs / FCM device token for this user.

    Actual push delivery requires the Apple Developer Program ($99) and an
    APNs key. This endpoint is the server-side groundwork: it stores the token
    so push delivery can be added in IOS-5+ without a schema change.

    Upserts on (user_id, token) so re-registration is idempotent.
    """
    conn.execute(
        """
        INSERT INTO device_push_tokens (user_id, token, platform, registered_at)
        VALUES (?, ?, ?, ?)
        ON CONFLICT(user_id, token) DO UPDATE SET
            platform = excluded.platform,
            registered_at = excluded.registered_at
        """,
        (user["id"], req.token, req.platform, datetime.now(UTC).isoformat()),
    )
    conn.commit()
