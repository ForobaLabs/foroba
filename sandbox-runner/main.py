"""FastAPI sandbox-runner: the only service with Docker API access, reached over the
internal `suite` network by Pazuru/Tsumi/Foroba. See docs/superpowers/specs/
2026-07-14-ti-b-item4-jeli-lab-sandbox-hardening-design.md.
"""
from __future__ import annotations

import base64
import hmac
import io
from typing import Any

import pandas as pd
from fastapi import FastAPI, Header, HTTPException
from pydantic import BaseModel

import sandbox_docker
from config import settings

app = FastAPI(title="Sandbox Runner")


class RunRequest(BaseModel):
    code: str
    dataframes: dict[str, str]  # name -> base64-encoded parquet bytes


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


def _check_token(supplied: str | None) -> None:
    expected = settings.sandbox_runner_token
    if not expected or not hmac.compare_digest((supplied or "").encode(), expected.encode()):
        raise HTTPException(status_code=403, detail="Forbidden")


@app.post("/run")
def run(
    request: RunRequest, x_sandbox_token: str | None = Header(default=None),
) -> dict[str, Any]:
    _check_token(x_sandbox_token)
    dataframes: dict[str, pd.DataFrame] = {}
    for name, encoded in request.dataframes.items():
        buf = io.BytesIO(base64.b64decode(encoded))
        dataframes[name] = pd.read_parquet(buf)
    return sandbox_docker.run_sandbox(request.code, dataframes)
