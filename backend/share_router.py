"""Goal what-if share links (Plan AQ D9, ID-07).

POST /share/goal   — authenticated: mint a 7-day signed link for a what-if.
GET  /share/goal/{token} — public, rate-limited, read-only: returns the signed payload.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, Field

import goal_share
from auth.dependencies import get_current_user
from rate_limit import limiter

router = APIRouter(prefix="/share", tags=["share"])


class GoalShareIn(BaseModel):
    name: str = Field(min_length=1, max_length=200)
    currency: str = Field(default="EUR", min_length=3, max_length=3)
    saved_cents: int = Field(ge=0, le=10**12)
    target_cents: int = Field(gt=0, le=10**12)
    monthly_cents: int = Field(ge=0, le=10**10)
    rate_pct: float = Field(ge=goal_share.RATE_MIN_PCT, le=goal_share.RATE_MAX_PCT)


@router.post("/goal", status_code=201)
@limiter.limit("20/hour")
def create_goal_share(
    request: Request,
    body: GoalShareIn,
    user: dict = Depends(get_current_user),
) -> dict:
    payload = goal_share.build_payload(**body.model_dump())
    token = goal_share.issue_token(payload)
    return {"token": token, "path": f"/share/goal/{token}", "expires_at": payload["exp"]}


@router.get("/goal/{token}")
@limiter.limit("60/minute")
def read_goal_share(request: Request, token: str) -> dict:
    try:
        return goal_share.verify_token(token)
    except goal_share.ShareTokenError as exc:
        raise HTTPException(status_code=400, detail="Invalid or expired share link") from exc
