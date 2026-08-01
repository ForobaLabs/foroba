"""Ollama code-gen + self-correction orchestration for Jeli Lab."""

from __future__ import annotations

import asyncio
import json
from collections.abc import AsyncGenerator
from typing import Any

import httpx
import pandas as pd

import sandbox_docker
from config import settings
from sandbox_guard import DisallowedImportError, check_imports

MAX_ATTEMPTS = 3

# Global concurrency cap on sandbox executions (foroba#189): guards against multiple
# simultaneous hosted-beta users each spinning up a 512MB sandbox container and
# exhausting the VPS's total RAM. Per-execution isolation (network none, read-only fs,
# non-root, ephemeral container) is handled in sandbox_docker.py; this caps how many of
# those isolated executions may run at once, server-wide.
_sandbox_semaphore = asyncio.Semaphore(settings.lab_sandbox_concurrency_limit)
SANDBOX_QUEUE_WAIT_SECONDS = 5

CODEGEN_SYSTEM_PROMPT = (
    "You are Jeli Lab, a data analyst that writes Python code against pandas "
    "DataFrames already loaded in the execution environment. Available "
    "DataFrames: {dataframe_names}. Set `result_text` (str) for a prose "
    "answer and/or `result_table` (pd.DataFrame) for a table. Use "
    "matplotlib.pyplot for charts (already imported as plt). Only use "
    "pandas, numpy, matplotlib, scipy, statsmodels, sklearn, math, "
    "statistics, datetime, json. Respond ONLY with JSON: "
    '{{"explanation": "...", "code": "..."}}'
)


def _chunk_words(text: str, size: int = 6) -> list[str]:
    words = text.split()
    return [" ".join(words[i : i + size]) for i in range(0, len(words), size)]


def _generate_code(
    question: str,
    dataframe_names: list[str],
    history: list[dict[str, Any]],
    user_context: str,
    error_feedback: str | None = None,
    web_results: list[dict[str, str]] | None = None,
) -> dict[str, str]:
    messages = [
        {
            "role": "system",
            "content": CODEGEN_SYSTEM_PROMPT.format(dataframe_names=", ".join(dataframe_names)),
        }
    ]
    if user_context:
        messages.append(
            {
                "role": "system",
                "content": f"What we know about this user: {user_context}",
            }
        )
    if web_results:
        summary = "\n".join(f"- {r['title']}: {r['snippet']} ({r['url']})" for r in web_results)
        messages.append({"role": "system", "content": f"Recent web search results:\n{summary}"})
    for turn in history:
        messages.append({"role": turn["role"], "content": turn["content"]})
    messages.append({"role": "user", "content": question})
    if error_feedback:
        messages.append(
            {
                "role": "user",
                "content": (
                    f"The previous code failed with this error, please fix it:\n{error_feedback}"
                ),
            }
        )

    response = httpx.post(
        f"{settings.ollama_base_url}/api/chat",
        json={
            "model": settings.ollama_model,
            "messages": messages,
            "format": "json",
            "stream": False,
        },
        timeout=60,
    )
    response.raise_for_status()
    content = response.json()["message"]["content"]
    return json.loads(content)


def _update_user_context(question: str, code: str, existing_context: str) -> str:
    try:
        response = httpx.post(
            f"{settings.ollama_base_url}/api/chat",
            json={
                "model": settings.ollama_model,
                "messages": [
                    {
                        "role": "system",
                        "content": (
                            "Update this user's durable profile notes in one short paragraph, "
                            "given their existing notes and their latest question. Respond with "
                            "plain text only, no JSON."
                        ),
                    },
                    {
                        "role": "user",
                        "content": (
                            f"Existing notes: {existing_context or '(none yet)'}\n"
                            f"Latest question: {question}"
                        ),
                    },
                ],
                "stream": False,
            },
            timeout=30,
        )
        response.raise_for_status()
        return response.json()["message"]["content"].strip()
    except Exception:
        return existing_context


async def _run_sandbox_limited(code: str, dataframes: dict[str, pd.DataFrame]) -> dict[str, Any]:
    """Run the sandbox dispatch behind the global concurrency cap.

    Fails fast (rather than queueing indefinitely) if the cap is already saturated for
    SANDBOX_QUEUE_WAIT_SECONDS, to avoid piling up blocked NDJSON streams under load.
    """
    try:
        await asyncio.wait_for(_sandbox_semaphore.acquire(), timeout=SANDBOX_QUEUE_WAIT_SECONDS)
    except TimeoutError:
        return {
            "ok": False,
            "busy": True,
            "error": "Jeli Lab is busy handling other requests, please try again shortly.",
            "traceback": "sandbox concurrency limit reached",
        }
    try:
        return await asyncio.to_thread(sandbox_docker.run_sandbox_dispatch, code, dataframes)
    finally:
        _sandbox_semaphore.release()


async def _attempt_turn(
    question: str,
    dataframe_names: list[str],
    dataframes: dict[str, pd.DataFrame],
    history: list[dict[str, Any]],
    user_context: str,
    error_feedback: str | None,
    web_results: list[dict[str, str]] | None = None,
) -> dict[str, Any]:
    """Generate code for one attempt, guard it, and run it in the sandbox.

    Returns a dict with either a successful sandbox result (`ok: True`) merged
    with `code`/`explanation`, or `{"ok": False, "code": ..., "error": ...}` on
    any failure (codegen error, disallowed import, or sandbox failure) so the
    caller's retry loop can feed the error back to the LLM.
    """
    try:
        generated = await asyncio.to_thread(
            _generate_code,
            question,
            dataframe_names,
            history,
            user_context,
            error_feedback,
            web_results,
        )
    except Exception as exc:
        return {"ok": False, "code": "", "error": str(exc)}

    code = generated.get("code", "")
    explanation = generated.get("explanation") or ""

    if not isinstance(code, str):
        return {
            "ok": False,
            "code": "",
            "error": f"Generated code was not valid Python source (got {type(code).__name__})",
        }

    try:
        check_imports(code)
    except (DisallowedImportError, SyntaxError) as exc:
        return {"ok": False, "code": code, "explanation": explanation, "error": str(exc)}

    result = await _run_sandbox_limited(code, dataframes)
    result["code"] = code
    result["explanation"] = explanation
    return result


async def _ensure_sandbox_ready() -> AsyncGenerator[dict[str, Any], None]:
    """Yield a 'starting_sandbox' status and start Docker if not already running.

    Yields nothing on success, or a final 'error' event if Docker could not be started.
    """
    if sandbox_docker.is_docker_running():
        return
    yield {"type": "status", "value": "starting_sandbox"}
    started = await sandbox_docker.ensure_docker_running()
    if not started:
        yield {
            "type": "error",
            "value": (
                "Couldn't start the local sandbox engine. Make sure Docker Desktop is installed."
            ),
        }


def _stream_success(result: dict[str, Any]) -> AsyncGenerator[dict[str, Any], None]:
    async def _gen():
        answer_text = result.get("text") or result.get("explanation", "")
        for chunk in _chunk_words(answer_text):
            yield {"type": "token", "value": chunk}
        for artifact in result.get("artifacts", []):
            yield {"type": "artifact", **artifact}

    return _gen()


async def run_lab_turn(
    question: str,
    dataframes: dict[str, pd.DataFrame],
    history: list[dict[str, Any]],
    user_context: str,
    web_results: list[dict[str, str]] | None = None,
) -> AsyncGenerator[dict[str, Any], None]:
    """Drive the generate-guard-run-retry loop for one chat turn, yielding NDJSON events."""
    async for event in _ensure_sandbox_ready():
        yield event
        if event["type"] == "error":
            return

    dataframe_names = list(dataframes)
    error_feedback: str | None = None
    code = ""

    for _attempt in range(MAX_ATTEMPTS):
        result = await _attempt_turn(
            question,
            dataframe_names,
            dataframes,
            history,
            user_context,
            error_feedback,
            web_results,
        )
        code = result.get("code", "")

        if result.get("ok"):
            async for event in _stream_success(result):
                yield event
            updated_context = await asyncio.to_thread(
                _update_user_context,
                question,
                code,
                user_context,
            )
            yield {"type": "done", "code": code, "context": updated_context}
            return

        if result.get("busy"):
            # Server-wide capacity issue, not a code problem — retrying codegen won't
            # help, so surface it immediately instead of burning the remaining attempts.
            yield {"type": "error", "value": result["error"], "code": code}
            return

        error_feedback = result.get("traceback") or result.get("error", "")

    yield {
        "type": "error",
        "value": "I couldn't complete that analysis — try rephrasing your question.",
        "code": code,
        "traceback": error_feedback,
    }
