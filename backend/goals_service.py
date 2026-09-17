"""Goals proxy service — Foroba's Goals widget now reads/writes real Pazuru
data instead of a localStorage mock (FOR-002).

The read path (list_goals) mirrors networth_service.py's degrade-gracefully
style: a Pazuru outage returns an empty list with degraded=True rather than
a hard error, since a transient outage should never crash the Goals page.

The write paths (create/update/delete) are a raw pass-through instead:
Pazuru's GoalCreate model validates target_cents/saved_cents (>= 0) and its
update/delete routes 404 when the goal doesn't exist or isn't owned by the
caller. Those are real, meaningful outcomes the caller must see — silently
degrading a failed write to "success" (or to null) would let the UI believe
a goal was created/updated when it wasn't — so failures are forwarded via
HTTPException carrying Pazuru's own status code and detail.
"""

from __future__ import annotations

import logging
from typing import Any

import httpx
from fastapi import HTTPException

from config import settings
from suite_cookies import suite_cookies

logger = logging.getLogger(__name__)

_TIMEOUT = 8.0


def _pazuru_base() -> str:
    return settings.pazuru_api_url.rstrip("/")


async def list_goals(*, cookie: str | None, stepup_pazuru: str | None) -> dict[str, Any]:
    cookies = suite_cookies(cookie, stepup_pazuru=stepup_pazuru)
    try:
        async with httpx.AsyncClient(timeout=_TIMEOUT) as client:
            resp = await client.get(f"{_pazuru_base()}/api/goals", cookies=cookies)
            resp.raise_for_status()
            return {"goals": resp.json(), "degraded": False}
    except Exception as exc:
        logger.warning("goals list unavailable: %s", exc)
        return {"goals": [], "degraded": True}


async def _proxy(
    method: str,
    path: str,
    *,
    cookie: str | None,
    stepup_pazuru: str | None,
    json_body: dict[str, Any] | None = None,
) -> Any:
    cookies = suite_cookies(cookie, stepup_pazuru=stepup_pazuru)
    try:
        async with httpx.AsyncClient(timeout=_TIMEOUT) as client:
            resp = await client.request(
                method, f"{_pazuru_base()}{path}", json=json_body, cookies=cookies
            )
    except Exception as exc:
        logger.warning("goals proxy unavailable (%s %s): %s", method, path, exc)
        raise HTTPException(502, "Goals service unavailable — please try again") from exc

    if resp.status_code >= 400:
        try:
            detail = resp.json().get("detail", resp.text)
        except Exception:
            detail = resp.text
        raise HTTPException(resp.status_code, detail)

    return None if resp.status_code == 204 else resp.json()


async def create_goal(
    body: dict[str, Any], *, cookie: str | None, stepup_pazuru: str | None
) -> Any:
    return await _proxy(
        "POST", "/api/goals", cookie=cookie, stepup_pazuru=stepup_pazuru, json_body=body
    )


async def update_goal(
    goal_id: int, body: dict[str, Any], *, cookie: str | None, stepup_pazuru: str | None
) -> Any:
    return await _proxy(
        "PUT",
        f"/api/goals/{goal_id}",
        cookie=cookie,
        stepup_pazuru=stepup_pazuru,
        json_body=body,
    )


async def delete_goal(goal_id: int, *, cookie: str | None, stepup_pazuru: str | None) -> None:
    await _proxy(
        "DELETE", f"/api/goals/{goal_id}", cookie=cookie, stepup_pazuru=stepup_pazuru
    )
