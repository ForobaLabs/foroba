"""Onboarding (MiFID questionnaire) and manual audience toggle."""
from __future__ import annotations

import sqlite3

from fastapi import APIRouter, Depends
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


@router.get("/onboarding/mifid")
def get_questionnaire() -> dict:
    return QUESTIONNAIRE


@router.post("/onboarding/mifid")
def submit(req: SubmitRequest,
           user: dict = Depends(get_current_user),
           conn: sqlite3.Connection = Depends(get_conn)) -> dict:
    audience = score_mifid(req.answers)
    repo.set_audience(conn, user["id"], audience, locked=True)
    return {"audience": audience, "locked": True}


@router.patch("/auth/audience")
def set_manual(req: AudienceRequest,
               user: dict = Depends(get_current_user),
               conn: sqlite3.Connection = Depends(get_conn)) -> dict:
    audience = "expert" if req.audience == "expert" else "base"
    repo.set_audience(conn, user["id"], audience, locked=False)
    return {"audience": audience, "locked": False}
