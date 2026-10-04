"""Push-based session-version invalidation to Pazuru/Tsumi (XAPP-D03).

Best-effort POST carrying the shared X-Internal-Token (foroba#299): Pazuru and
Tsumi reject the call without it, so an anonymous caller cannot raise a user's
session floor. Does not block/fail logout if a downstream app is unreachable
(logout must always succeed locally).
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

    Skipped with a warning when INTERNAL_API_TOKEN is unset (downstream would 403).
    """
    token = settings.internal_api_token
    if not token:
        logger.warning("INTERNAL_API_TOKEN unset; skipping session-invalidate push for %s", user_id)
        return
    for base in (settings.pazuru_api_url, settings.tsumi_api_url):
        url = f"{base.rstrip('/')}/internal/session-invalidate"
        try:
            httpx.post(
                url,
                json={"user_id": user_id, "min_version": new_version},
                headers={"X-Internal-Token": token},
                timeout=2,
            )
        except httpx.HTTPError as exc:
            logger.warning("session-invalidate push failed for %s: %s", url, exc)
