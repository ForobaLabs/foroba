"""Goals proxy routes — real per-account data from Pazuru (FOR-002)."""

from __future__ import annotations

from fastapi import APIRouter, Cookie, Depends
from pydantic import BaseModel, Field

import goals_service
from auth.dependencies import get_current_user
from stepup import issue_stepup_cookies

router = APIRouter(prefix="/goals", tags=["goals"])


class GoalIn(BaseModel):
    name: str
    target_cents: int = Field(ge=0)
    saved_cents: int = Field(default=0, ge=0)
    currency: str = "EUR"
    deadline: str | None = None
    monthly_contribution_cents: int = 0


@router.get("")
async def list_goals(
    user: dict = Depends(get_current_user),
    suite_session: str | None = Cookie(default=None),
) -> dict:
    """FOR-002: real per-account goals proxied from Pazuru, replacing the
    localStorage mock. No entitlement gating — Goals has no REGISTRY entry
    in auth/entitlements.py, so this route only requires auth."""
    stepup = issue_stepup_cookies(user["id"])
    return await goals_service.list_goals(cookie=suite_session, stepup_pazuru=stepup["pazuru"])


@router.post("", status_code=201)
async def create_goal(
    body: GoalIn,
    user: dict = Depends(get_current_user),
    suite_session: str | None = Cookie(default=None),
) -> dict:
    stepup = issue_stepup_cookies(user["id"])
    return await goals_service.create_goal(
        body.model_dump(), cookie=suite_session, stepup_pazuru=stepup["pazuru"]
    )


@router.put("/{goal_id}")
async def update_goal(
    goal_id: int,
    body: GoalIn,
    user: dict = Depends(get_current_user),
    suite_session: str | None = Cookie(default=None),
) -> dict:
    stepup = issue_stepup_cookies(user["id"])
    return await goals_service.update_goal(
        goal_id, body.model_dump(), cookie=suite_session, stepup_pazuru=stepup["pazuru"]
    )


@router.delete("/{goal_id}", status_code=204)
async def delete_goal(
    goal_id: int,
    user: dict = Depends(get_current_user),
    suite_session: str | None = Cookie(default=None),
) -> None:
    stepup = issue_stepup_cookies(user["id"])
    await goals_service.delete_goal(goal_id, cookie=suite_session, stepup_pazuru=stepup["pazuru"])
