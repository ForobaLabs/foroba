"""Jeli Lab: /lab/chat NDJSON streaming, aggregating Pazuru + Tsumi data."""
from __future__ import annotations

import json

from fastapi import APIRouter, Cookie, Depends
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

from auth.conn import get_conn
from auth.dependencies import get_current_user
from config import settings
from db import (
    get_sandbox_history,
    get_sandbox_user_context,
    save_sandbox_turn,
    update_sandbox_user_context,
)
from lab_data_aggregator import gather_dataframes
from lab_service import run_lab_turn
from searxng_client import search_web
from settings_store import get_all

router = APIRouter(prefix="/lab", tags=["lab"])


class LabChatRequest(BaseModel):
    message: str
    session_id: str
    allow_internet: bool = False


@router.post("/chat")
async def lab_chat(
    body: LabChatRequest,
    user: dict = Depends(get_current_user),
    conn=Depends(get_conn),
    suite_session: str | None = Cookie(default=None),
):
    user_id = str(user["id"])

    if get_all(conn).get("lab_service_enabled", "true") == "false":
        async def _disabled_stream():
            yield json.dumps({
                "type": "error",
                "value": "Jeli Lab is currently unavailable. Please try again later.",
            }) + "\n"
        return StreamingResponse(_disabled_stream(), media_type="application/x-ndjson")

    dataframes = await gather_dataframes(
        settings.pazuru_api_url, settings.tsumi_api_url, cookie=suite_session
    )
    history = get_sandbox_history(conn, user_id, body.session_id)
    context = get_sandbox_user_context(conn, user_id)

    web_results = None
    search_note = None
    if body.allow_internet:
        web_results = await search_web(body.message, settings.searxng_url)
        if not web_results:
            search_note = "Web search was unavailable for this answer."

    async def _stream():
        code = None
        artifacts: list[dict] = []
        answer_parts: list[str] = []
        error_message: str | None = None
        async for event in run_lab_turn(
            question=body.message, dataframes=dataframes, history=history, user_context=context,
            web_results=web_results,
        ):
            if event["type"] == "token":
                answer_parts.append(event["value"])
            elif event["type"] == "artifact":
                artifacts.append(event)
            elif event["type"] == "done":
                code = event.get("code")
                if event.get("context"):
                    update_sandbox_user_context(conn, user_id, event["context"])
            elif event["type"] == "error":
                code = event.get("code")
                error_message = event["value"]
            yield json.dumps(event) + "\n"

        if search_note:
            yield json.dumps({"type": "token", "value": f" ({search_note})"}) + "\n"

        if code is not None:
            save_sandbox_turn(
                conn, user_id, body.session_id, body.message,
                error_message or " ".join(answer_parts), code=code, artifacts_json=json.dumps(artifacts),
            )

    return StreamingResponse(_stream(), media_type="application/x-ndjson")
