"""Cross-app session handoff — mint endpoint (Plan U, pazuru#150).

A plain GET so a bare `<a href>` from the Foroba shell works with no JS: the
browser navigates here with the user's existing suite_session/stepup_<app>
cookies attached, we mint an opaque one-time code, and 302 the browser to the
target app's own /auth/handoff consumer (reached via the already-mounted
/api/v1/<app>/ versioned proxy, so it works from any of the three domains). The
consumer redeems the code back-channel via `POST /internal/handoff/redeem`
(shared X-Internal-Token), sets its own domain-scoped cookies and redirects on to
the originally-intended page. No session material ever appears in a URL.

Plan AU L-3 (login CSRF): every code is bound to a `nonce` that the consumer app first
set as an httponly cookie in this same browser (its `/auth/handoff/start`), and the
consumer refuses a code whose nonce doesn't match. A request without a nonce (the
shell's plain links) is bounced to the consumer's start route, which comes back here
with one.
"""

from __future__ import annotations

import hmac
import re

from fastapi import APIRouter, Cookie, Depends, Header, HTTPException, Query, Request
from fastapi.responses import RedirectResponse
from pydantic import BaseModel

from auth.dependencies import get_current_user
from config import settings
from handoff import VALID_APPS, HandoffTokenError, issue_handoff_code, redeem_handoff_code
from rate_limit import limiter

router = APIRouter(prefix="/auth/handoff", tags=["handoff"])

_APP_URLS = {
    "pazuru": lambda: settings.pazuru_app_url,
    "tsumi": lambda: settings.tsumi_app_url,
}

# Same-origin internal path only — no scheme, no host, no protocol-relative "//".
_SAFE_REDIRECT = re.compile(r"^/(?!/)[A-Za-z0-9/_.-]*$")
_NONCE = re.compile(r"^[A-Za-z0-9_-]{32,64}$")


@router.get("/{app}")
@limiter.limit("30/minute")
def handoff_mint(
    request: Request,
    app: str,
    redirect: str = Query(default="/"),
    nonce: str | None = Query(default=None),
    user: dict = Depends(get_current_user),
    suite_session: str | None = Cookie(default=None),
) -> RedirectResponse:
    if app not in VALID_APPS:
        raise HTTPException(404, "Unknown app")
    if not suite_session:
        raise HTTPException(401, "Not authenticated")
    if not _SAFE_REDIRECT.match(redirect):
        redirect = "/"
    if nonce is None:
        start = f"{_APP_URLS[app]()}/api/v1/{app}/auth/handoff/start?redirect={redirect}"
        return RedirectResponse(url=start, status_code=302)
    if not _NONCE.match(nonce):
        raise HTTPException(400, "Invalid handoff nonce")

    stepup_token = request.cookies.get(f"stepup_{app}")
    code = issue_handoff_code(
        user_id=user["id"],
        app=app,
        redirect=redirect,
        sess=suite_session,
        stepup=stepup_token,
        nonce=nonce,
    )
    target = f"{_APP_URLS[app]()}/api/v1/{app}/auth/handoff?code={code}"
    return RedirectResponse(url=target, status_code=302)


def _require_internal_token(x_internal_token: str = Header(default="")) -> None:
    """Fail closed: reject unless X-Internal-Token matches INTERNAL_API_TOKEN."""
    expected = settings.internal_api_token
    if not expected or not hmac.compare_digest(x_internal_token.encode(), expected.encode()):
        raise HTTPException(status_code=403, detail="forbidden")


class RedeemRequest(BaseModel):
    code: str
    app: str


internal_router = APIRouter(
    prefix="/internal/handoff", tags=["handoff"], dependencies=[Depends(_require_internal_token)]
)


@internal_router.post("/redeem")
def handoff_redeem(req: RedeemRequest) -> dict:
    """Back-channel redemption by Pazuru/Tsumi; the code is consumed on first use."""
    try:
        return redeem_handoff_code(req.code, expected_app=req.app)
    except HandoffTokenError as exc:
        raise HTTPException(401, "Invalid, expired or already used handoff code") from exc
