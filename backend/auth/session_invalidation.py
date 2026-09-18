"""Push-based session-version invalidation to Pazuru/Tsumi (XAPP-D03).

Mirrors admin_router.py's `_invalidate_downstream_settings_caches()` pattern
exactly: unauthenticated best-effort POST, does not block/fail logout if a
downstream app is unreachable (logout must always succeed locally; the
downstream app's own version-floor cache just won't be refreshed until the
next successful push). The settings-cache precedent is unauthenticated
because its worst case is a forced cheap re-poll; here the worst case of an
unauthenticated caller is a forced extra login for one user id -- a
revoke-only action, never a privilege grant, so the same trust model
applies (see this module's docstring note under `invalidate_sessions_
downstream` for the accepted risk).
"""

from __future__ import annotations

import logging

import httpx

from config import settings

logger = logging.getLogger(__name__)


def invalidate_sessions_downstream(user_id: int, new_version: int) -> None:
    """Best-effort push of the new session_version floor to Pazuru and Tsumi
    so their own require_auth() rejects any already-issued suite_session
    JWT for user_id below new_version, without waiting for that JWT's own
    exp claim. Never raises -- same resilience posture as the settings-cache
    invalidation this mirrors.

    Accepted risk (matches the settings-cache precedent's own trust model,
    confirmed via admin_router.py / pazuru's routers/jeli.py / tsumi's
    api/routes/jeli.py: none of these internal endpoints carry a shared-
    secret or other internal-auth header): an unauthenticated caller could
    POST arbitrary (user_id, min_version) pairs to force a login-required
    state for any user id. This is a revoke-only DoS surface (forces an
    extra real login), not a privilege escalation or data-disclosure risk --
    the same severity class the settings-cache endpoint's own docstring
    already accepts ("worst case a caller forces an extra cheap re-poll").
    """
    for base in (settings.pazuru_api_url, settings.tsumi_api_url):
        url = f"{base.rstrip('/')}/internal/session-invalidate"
        try:
            httpx.post(url, json={"user_id": user_id, "min_version": new_version}, timeout=2)
        except httpx.HTTPError as exc:
            logger.warning("session-invalidate push failed for %s: %s", url, exc)
