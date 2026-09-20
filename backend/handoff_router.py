"""Cross-app session handoff — mint endpoint (Plan U, pazuru#150).

A plain GET so a bare `<a href>` from the Foroba shell works with no JS: the
browser navigates here with the user's existing suite_session/stepup_<app>
cookies attached, we mint a short-lived handoff token embedding those values,
and 302 the browser straight to the target app's own /auth/handoff consumer
(reached via the already-mounted /api/v1/<app>/ versioned proxy, so it works
from any of the three domains) — which sets its own domain-scoped cookies and
redirects on to the originally-intended page.
"""

from __future__ import annotations

import re

from fastapi import APIRouter, Cookie, Depends, HTTPException, Query, Request
from fastapi.responses import RedirectResponse

from auth.dependencies import get_current_user
from config import settings
from handoff import VALID_APPS, issue_handoff_token
from rate_limit import limiter

router = APIRouter(prefix="/auth/handoff", tags=["handoff"])

_APP_URLS = {
    "pazuru": lambda: settings.pazuru_app_url,
    "tsumi": lambda: settings.tsumi_app_url,
}

# Same-origin internal path only — no scheme, no host, no protocol-relative "//".
_SAFE_REDIRECT = re.compile(r"^/(?!/)[A-Za-z0-9/_.-]*$")


@router.get("/{app}")
@limiter.limit("30/minute")
def handoff_mint(
    request: Request,
    app: str,
    redirect: str = Query(default="/"),
    user: dict = Depends(get_current_user),
    suite_session: str | None = Cookie(default=None),
) -> RedirectResponse:
    if app not in VALID_APPS:
        raise HTTPException(404, "Unknown app")
    if not suite_session:
        raise HTTPException(401, "Not authenticated")
    if not _SAFE_REDIRECT.match(redirect):
        redirect = "/"

    stepup_token = request.cookies.get(f"stepup_{app}")
    token = issue_handoff_token(
        user_id=user["id"],
        app=app,
        redirect=redirect,
        sess=suite_session,
        stepup=stepup_token,
    )
    target = f"{_APP_URLS[app]()}/api/v1/{app}/auth/handoff?token={token}"
    return RedirectResponse(url=target, status_code=302)
