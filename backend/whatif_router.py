"""What-if simulator routes: live preview + saveable named scenarios
(foroba#162, TI-D item 1)."""

from __future__ import annotations

import json
import sqlite3

from fastapi import APIRouter, Cookie, Depends, HTTPException
from pydantic import BaseModel

import db
import whatif_service
from auth.conn import get_conn
from auth.entitlements_router import require_feature
from stepup import issue_stepup_cookies

router = APIRouter(prefix="/whatif", tags=["whatif"])

FEATURE_KEY = "household.whatif_simulator"


class OneOffEvent(BaseModel):
    month_offset: int
    amount_cents: int
    label: str


class GoalContribution(BaseModel):
    goal_id: int
    extra_monthly_cents: int


class SimulateParams(BaseModel):
    horizon_months: int = 24
    eliminate_categories: list[str] | None = None
    reduce_merchant_pct: dict[str, float] | None = None
    income_delta_cents: int = 0
    goal_contributions: list[GoalContribution] = []
    one_off_events: list[OneOffEvent] = []
    investment_growth_rate_pct: float = 5.0


@router.post("/simulate")
async def simulate(
    body: SimulateParams,
    user: dict = Depends(require_feature(FEATURE_KEY)),
    suite_session: str | None = Cookie(default=None),
) -> dict:
    stepup = issue_stepup_cookies(user["id"])
    return await whatif_service.simulate(
        body.model_dump(),
        body.horizon_months,
        owner_cookie=suite_session,
        stepup_pazuru=stepup["pazuru"],
        stepup_tsumi=stepup["tsumi"],
    )


class ScenarioIn(BaseModel):
    name: str
    horizon_months: int
    params: SimulateParams


class ScenarioOut(BaseModel):
    id: int
    name: str
    horizon_months: int
    params: dict
    created_at: str
    updated_at: str


def _to_out(row: sqlite3.Row) -> ScenarioOut:
    return ScenarioOut(
        id=row["id"],
        name=row["name"],
        horizon_months=row["horizon_months"],
        params=json.loads(row["params_json"]),
        created_at=row["created_at"],
        updated_at=row["updated_at"],
    )


@router.get("/scenarios")
def list_scenarios(
    user: dict = Depends(require_feature(FEATURE_KEY)),
    conn: sqlite3.Connection = Depends(get_conn),
) -> list[ScenarioOut]:
    rows = db.list_whatif_scenarios(conn, user_id=user["id"], household_id=user.get("household_id"))
    return [_to_out(r) for r in rows]


@router.post("/scenarios", status_code=201)
def create_scenario(
    body: ScenarioIn,
    user: dict = Depends(require_feature(FEATURE_KEY)),
    conn: sqlite3.Connection = Depends(get_conn),
) -> ScenarioOut:
    row = db.create_whatif_scenario(
        conn,
        created_by_user_id=user["id"],
        household_id=user.get("household_id"),
        name=body.name,
        horizon_months=body.horizon_months,
        params_json=json.dumps(body.params.model_dump()),
    )
    return _to_out(row)


@router.get("/scenarios/{scenario_id}")
async def get_scenario(
    scenario_id: int,
    user: dict = Depends(require_feature(FEATURE_KEY)),
    conn: sqlite3.Connection = Depends(get_conn),
    suite_session: str | None = Cookie(default=None),
) -> dict:
    row = db.get_whatif_scenario(
        conn, scenario_id, user_id=user["id"], household_id=user.get("household_id")
    )
    if row is None:
        raise HTTPException(404, "Scenario not found")
    stepup = issue_stepup_cookies(user["id"])
    params = json.loads(row["params_json"])
    projection = await whatif_service.simulate(
        params,
        row["horizon_months"],
        owner_cookie=suite_session,
        stepup_pazuru=stepup["pazuru"],
        stepup_tsumi=stepup["tsumi"],
    )
    return {**_to_out(row).model_dump(), "projection": projection}


@router.put("/scenarios/{scenario_id}")
def update_scenario(
    scenario_id: int,
    body: ScenarioIn,
    user: dict = Depends(require_feature(FEATURE_KEY)),
    conn: sqlite3.Connection = Depends(get_conn),
) -> ScenarioOut:
    row = db.update_whatif_scenario(
        conn,
        scenario_id,
        user_id=user["id"],
        household_id=user.get("household_id"),
        name=body.name,
        horizon_months=body.horizon_months,
        params_json=json.dumps(body.params.model_dump()),
    )
    if row is None:
        raise HTTPException(404, "Scenario not found")
    return _to_out(row)


@router.delete("/scenarios/{scenario_id}", status_code=204)
def delete_scenario(
    scenario_id: int,
    user: dict = Depends(require_feature(FEATURE_KEY)),
    conn: sqlite3.Connection = Depends(get_conn),
) -> None:
    if not db.delete_whatif_scenario(
        conn, scenario_id, user_id=user["id"], household_id=user.get("household_id")
    ):
        raise HTTPException(404, "Scenario not found")
