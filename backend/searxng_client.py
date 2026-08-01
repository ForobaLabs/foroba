"""Opt-in web search via a self-hosted SearXNG instance for Jeli Lab.

Results are summarized into the LLM prompt only — never passed to the sandbox
execution environment, and the sandbox container never gains network access.
"""

from __future__ import annotations

import logging

import httpx

logger = logging.getLogger(__name__)

MAX_RESULTS = 5


async def search_web(query: str, searxng_url: str) -> list[dict[str, str]]:
    try:
        async with httpx.AsyncClient() as client:
            resp = await client.get(
                f"{searxng_url}/search",
                params={"q": query, "format": "json"},
                timeout=5.0,
            )
            resp.raise_for_status()
            data = resp.json()
        return [
            {"title": r.get("title", ""), "snippet": r.get("content", ""), "url": r.get("url", "")}
            for r in data.get("results", [])[:MAX_RESULTS]
        ]
    except Exception as exc:  # system boundary: SearXNG may be offline
        logger.warning("SearXNG search unavailable: %s", exc)
        return []
