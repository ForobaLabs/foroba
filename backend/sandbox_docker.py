"""Docker lifecycle for the Jeli Lab sandbox: auto-start, container run, cleanup."""

from __future__ import annotations

import asyncio
import base64
import io
import json
import platform
import shutil
import subprocess
import tempfile
from pathlib import Path
from typing import Any

import httpx
import pandas as pd

from config import settings

DOCKER_INFO_TIMEOUT_SECONDS = 5
DOCKER_START_MAX_WAIT_SECONDS = 45
DOCKER_START_POLL_INTERVAL_SECONDS = 2
CONTAINER_RUN_TIMEOUT_SECONDS = 15


def is_docker_running() -> bool:
    """Return True if the Docker daemon responds to `docker info`.

    Always True when SANDBOX_RUNNER_URL is set: in that mode this container has no Docker
    CLI/daemon at all — sandbox execution is delegated entirely to the sandbox-runner sidecar,
    which manages its own Docker readiness (foroba#120).
    """
    if settings.sandbox_runner_url:
        return True
    try:
        subprocess.run(
            ["docker", "info"],
            capture_output=True,
            timeout=DOCKER_INFO_TIMEOUT_SECONDS,
            check=True,
        )
        return True
    except (subprocess.CalledProcessError, subprocess.TimeoutExpired, FileNotFoundError):
        return False


async def ensure_docker_running(max_wait_seconds: int = DOCKER_START_MAX_WAIT_SECONDS) -> bool:
    """Return True once Docker responds, starting Docker Desktop if needed (macOS only)."""
    if is_docker_running():
        return True
    if platform.system() == "Darwin":
        subprocess.run(["open", "-a", "Docker"], capture_output=True)
    waited = 0
    while waited < max_wait_seconds:
        await asyncio.sleep(DOCKER_START_POLL_INTERVAL_SECONDS)
        waited += DOCKER_START_POLL_INTERVAL_SECONDS
        if is_docker_running():
            return True
    return False


def run_sandbox(code: str, dataframes: dict[str, pd.DataFrame]) -> dict[str, Any]:
    """Run `code` against `dataframes` in an isolated container. Returns the parsed JSON result.

    Resource/network hardening (foroba#132): `--network none` (no network access at all),
    `--memory=512m` + `--cpus=1` + `--pids-limit=64` + `--ulimit cpu=10` (bound memory/CPU/
    fork-bomb exposure), `--read-only` + `--tmpfs /tmp` (no writable filesystem outside
    /tmp), `--user sandboxuser` (non-root), plus `sandbox_guard.py`'s AST import whitelist
    as a first-pass reject before the container even starts. This is defense-in-depth, not
    a 100%-secure sandbox — a container escape or an unpatched Docker/kernel vulnerability
    could still defeat these limits. Do not rely on this alone for untrusted/adversarial code
    from outside the local trusted household; it is designed to contain AI-generated analysis
    code, not to be a hardened multi-tenant execution service.
    """
    workspace = tempfile.mkdtemp()
    try:
        workspace_path = Path(workspace)
        (workspace_path / "code.py").write_text(code)
        data_dir = workspace_path / "data"
        data_dir.mkdir(exist_ok=True)
        for name, df in dataframes.items():
            df.to_parquet(data_dir / f"{name}.parquet")

        cmd = [
            "docker",
            "run",
            "--rm",
            "--network",
            "none",
            "--read-only",
            "--tmpfs",
            "/tmp:size=64m",
            "--memory=512m",
            "--cpus=1",
            "--pids-limit=64",
            "--ulimit",
            "cpu=10",
            "--user",
            "sandboxuser",
            "-v",
            f"{workspace}:/workspace:ro",
            settings.sandbox_image,
        ]
        try:
            proc = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=CONTAINER_RUN_TIMEOUT_SECONDS,
            )
            last_line = proc.stdout.strip().splitlines()[-1] if proc.stdout.strip() else "{}"
            return json.loads(last_line)
        except subprocess.TimeoutExpired:
            return {
                "ok": False,
                "error": "Sandbox execution timed out",
                "traceback": "Sandbox execution timed out",
            }
        except Exception as exc:
            return {"ok": False, "error": str(exc), "traceback": str(exc)}
    finally:
        shutil.rmtree(workspace, ignore_errors=True)


def run_sandbox_dispatch(code: str, dataframes: dict[str, pd.DataFrame]) -> dict[str, Any]:
    """Entry point used by lab_service.py. Routes to the sandbox-runner sidecar when
    SANDBOX_RUNNER_URL is configured (containerized deployment), otherwise falls back to
    the direct local Docker CLI path (bare-process local dev, unchanged since SP23)."""
    if settings.sandbox_runner_url:
        return _run_sandbox_remote(code, dataframes)
    return run_sandbox(code, dataframes)


def _run_sandbox_remote(code: str, dataframes: dict[str, pd.DataFrame]) -> dict[str, Any]:
    """POST code + dataframes (base64 parquet) to the sandbox-runner sidecar over HTTP."""
    encoded: dict[str, str] = {}
    for name, df in dataframes.items():
        buf = io.BytesIO()
        df.to_parquet(buf)
        encoded[name] = base64.b64encode(buf.getvalue()).decode("ascii")
    try:
        resp = httpx.post(
            f"{settings.sandbox_runner_url}/run",
            json={"code": code, "dataframes": encoded},
            headers={"X-Sandbox-Token": settings.sandbox_runner_token},
            timeout=CONTAINER_RUN_TIMEOUT_SECONDS + 5,
        )
        resp.raise_for_status()
        return resp.json()
    except httpx.HTTPError as exc:
        return {"ok": False, "error": str(exc), "traceback": str(exc)}
