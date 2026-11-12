"""Onboarding (MiFID questionnaire) and manual audience toggle."""

from __future__ import annotations

import sqlite3

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from auth import repository as repo
from auth.conn import get_conn
from auth.dependencies import get_current_user
from onboarding.mifid import QUESTIONNAIRE, score_mifid

router = APIRouter(tags=["onboarding"])


class SubmitRequest(BaseModel):
    answers: dict[str, int]


class AudienceRequest(BaseModel):
    audience: str  # "base" | "expert"


def _validate_answers(answers: dict[str, int]) -> None:
    """Every question answered with an in-range option index, else 422 (never a 500)."""
    for q in QUESTIONNAIRE["questions"]:
        idx = answers.get(q["id"])
        if idx is None or not 0 <= idx < len(q["options"]):
            raise HTTPException(
                status_code=422, detail=f"Invalid or missing answer for '{q['id']}'"
            )


@router.get("/onboarding/mifid")
def get_questionnaire() -> dict:
    return QUESTIONNAIRE


@router.post("/onboarding/mifid")
def submit(
    req: SubmitRequest,
    user: dict = Depends(get_current_user),
    conn: sqlite3.Connection = Depends(get_conn),
) -> dict:
    _validate_answers(req.answers)
    audience = score_mifid(req.answers)
    repo.set_audience(conn, user["id"], audience, locked=True)
    return {"audience": audience, "locked": True}


@router.patch("/auth/audience")
def set_manual(
    req: AudienceRequest,
    user: dict = Depends(get_current_user),
    conn: sqlite3.Connection = Depends(get_conn),
) -> dict:
    audience = "expert" if req.audience == "expert" else "base"
    repo.set_audience(conn, user["id"], audience, locked=False)
    return {"audience": audience, "locked": False}
