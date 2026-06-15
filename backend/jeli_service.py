"""Jeli service — context gathering + Ollama interaction."""
from __future__ import annotations

import asyncio
import json
import logging
from pathlib import Path
from typing import AsyncIterator

import httpx

from config import settings

logger = logging.getLogger(__name__)

PROMPT_TEMPLATE = (Path(__file__).parent / "prompts" / "jeli_system.txt").read_text()


# ---------------------------------------------------------------------------
# Personality helpers
# ---------------------------------------------------------------------------

def _tone_label(value: int) -> str:
    if value <= 2:
        return "Analytical & precise"
    if value <= 5:
        return "Balanced"
    if value <= 8:
        return "Warm & encouraging"
    return "Griot storyteller"


def _tone_description(value: int) -> str:
    if value <= 2:
        return "Be concise, data-driven, and use precise financial language."
    if value <= 5:
        return "Balance data with clear explanations."
    if value <= 8:
        return "Be warm and encouraging. Use real-life analogies."
    return "Tell financial stories like a griot. Use vivid language and cultural references."


def _expertise_label(value: int) -> str:
    return "Financial expert" if value >= 7 else ("Intermediate" if value >= 4 else "Beginner-friendly")


def _expertise_description(value: int) -> str:
    if value <= 2:
        return "Explain all terms. Avoid jargon. Use simple language."
    if value <= 6:
        return "Use standard financial terms but briefly explain less common ones."
    return "Use full financial/investment terminology without simplification."


# ---------------------------------------------------------------------------
# Context gathering
# ---------------------------------------------------------------------------

async def _fetch_context(client: httpx.AsyncClient, url: str, label: str) -> str:
    try:
        resp = await client.get(url, timeout=3.0)
        resp.raise_for_status()
        data = resp.json()
        return json.dumps(data, indent=2)
    except Exception as exc:
        logger.warning("%s context unavailable: %s", label, exc)
        return f"{label} is currently offline — no data available."


async def gather_context(pazuru_url: str, tsumi_url: str) -> tuple[str, str]:
    async with httpx.AsyncClient() as client:
        pazuru_task = _fetch_context(client, f"{pazuru_url}/jeli/context", "Pazuru")
        tsumi_task = _fetch_context(client, f"{tsumi_url}/jeli/context", "Tsumi")
        pazuru_ctx, tsumi_ctx = await asyncio.gather(pazuru_task, tsumi_task)
    return pazuru_ctx, tsumi_ctx


# ---------------------------------------------------------------------------
# System prompt builder
# ---------------------------------------------------------------------------

def build_system_prompt(
    pazuru_context: str,
    tsumi_context: str,
    user_name: str,
    tone: int,
    expertise: int,
) -> str:
    return PROMPT_TEMPLATE.format(
        user_name=user_name or "the user",
        personality_tone_label=_tone_label(tone),
        personality_tone_description=_tone_description(tone),
        expertise_level_label=_expertise_label(expertise),
        expertise_level_description=_expertise_description(expertise),
        pazuru_context=pazuru_context,
        tsumi_context=tsumi_context,
    )


# ---------------------------------------------------------------------------
# Ollama streaming
# ---------------------------------------------------------------------------

async def stream_chat(system_prompt: str, message: str) -> AsyncIterator[str]:
    payload = {
        "model": settings.ollama_model,
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": message},
        ],
        "stream": True,
    }
    async with httpx.AsyncClient(timeout=None) as client:
        async with client.stream(
            "POST",
            f"{settings.ollama_base_url}/api/chat",
            json=payload,
        ) as response:
            response.raise_for_status()
            async for line in response.aiter_lines():
                if not line:
                    continue
                try:
                    chunk = json.loads(line)
                    content = chunk.get("message", {}).get("content", "")
                    if content:
                        yield content
                    if chunk.get("done"):
                        break
                except json.JSONDecodeError:
                    continue
