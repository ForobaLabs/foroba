"""Cross-app data aggregation for Jeli Lab: fetches DataFrames from Pazuru + Tsumi.

Mirrors jeli_service._fetch_context / gather_context's graceful-fallback pattern,
but returns full DataFrames (decoded from base64 parquet) instead of a text summary,
since Lab needs to compute on the data, not just describe it.
"""

from __future__ import annotations

import asyncio
import base64
import io
import logging

import httpx
import pandas as pd

from suite_cookies import suite_cookies

logger = logging.getLogger(__name__)


async def _fetch_export(
    client: httpx.AsyncClient, url: str, prefix: str, cookies: dict[str, str] | None
) -> dict[str, pd.DataFrame]:
    try:
        resp = await client.get(url, cookies=cookies, timeout=5.0)
        resp.raise_for_status()
        encoded = resp.json()
        return {
            f"{prefix}_{name}": pd.read_parquet(io.BytesIO(base64.b64decode(b64)))
            for name, b64 in encoded.items()
        }
    except Exception as exc:
        logger.warning("%s export unavailable: %s", prefix, exc)
        return {}


async def gather_dataframes(
    pazuru_url: str,
    tsumi_url: str,
    cookie: str | None,
    *,
    stepup_pazuru: str | None = None,
    stepup_tsumi: str | None = None,
) -> dict[str, pd.DataFrame]:
    cookies = suite_cookies(cookie, stepup_pazuru=stepup_pazuru, stepup_tsumi=stepup_tsumi)
    async with httpx.AsyncClient() as client:
        pazuru_task = _fetch_export(client, f"{pazuru_url}/api/lab/export", "pazuru", cookies)
        tsumi_task = _fetch_export(client, f"{tsumi_url}/api/lab/export", "tsumi", cookies)
        pazuru_dfs, tsumi_dfs = await asyncio.gather(pazuru_task, tsumi_task)
    return {**pazuru_dfs, **tsumi_dfs}
