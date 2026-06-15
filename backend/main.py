"""Foroba Jeli backend — FastAPI microservice for unified AI assistant.

Start:
    uvicorn main:app --host 127.0.0.1 --port 8002 --reload
"""
from __future__ import annotations

import logging
from typing import Annotated

from fastapi import FastAPI, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field

from config import settings
from jeli_service import build_system_prompt, gather_context, stream_chat

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI(
    title="Foroba Jeli API",
    description="Unified local LLM assistant — cross-domain financial advisor",
    version="0.1.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://localhost:5174"],
    allow_methods=["*"],
    allow_headers=["*"],
)


class Personality(BaseModel):
    tone: Annotated[int, Field(ge=0, le=10)] = 5
    expertise: Annotated[int, Field(ge=0, le=10)] = 5


class ChatRequest(BaseModel):
    message: str = Field(..., min_length=1, max_length=4000)
    user_name: str = "User"
    personality: Personality = Personality()


@app.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok", "service": "foroba-jeli", "version": "0.1.0"}


@app.post("/jeli/chat")
async def jeli_chat(req: ChatRequest) -> StreamingResponse:
    """Stream a Jeli response for the given message.

    Gathers context from Pazuru + Tsumi, builds the system prompt,
    then streams the Ollama response as plain text chunks (SSE-compatible).
    """
    pazuru_ctx, tsumi_ctx = await gather_context(
        settings.pazuru_api_url,
        settings.tsumi_api_url,
    )
    system_prompt = build_system_prompt(
        pazuru_context=pazuru_ctx,
        tsumi_context=tsumi_ctx,
        user_name=req.user_name,
        tone=req.personality.tone,
        expertise=req.personality.expertise,
    )

    async def generate():
        async for chunk in stream_chat(system_prompt, req.message):
            yield chunk

    return StreamingResponse(generate(), media_type="text/plain; charset=utf-8")
