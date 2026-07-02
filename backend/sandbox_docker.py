"""Docker lifecycle for the Jeli Lab sandbox: auto-start, container run, cleanup."""
from __future__ import annotations

import asyncio
import json
import platform
import shutil
import subprocess
import tempfile
from pathlib import Path
from typing import Any

import pandas as pd

from config import settings

DOCKER_INFO_TIMEOUT_SECONDS = 5
DOCKER_START_MAX_WAIT_SECONDS = 45
DOCKER_START_POLL_INTERVAL_SECONDS = 2
CONTAINER_RUN_TIMEOUT_SECONDS = 15


def is_docker_running() -> bool:
    """Return True if the Docker daemon responds to `docker info`."""
    try:
        subprocess.run(
            ["docker", "info"], capture_output=True,
            timeout=DOCKER_INFO_TIMEOUT_SECONDS, check=True,
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
    """Run `code` against `dataframes` in an isolated container. Returns the parsed JSON result."""
    workspace = tempfile.mkdtemp()
    try:
        workspace_path = Path(workspace)
        (workspace_path / "code.py").write_text(code)
        data_dir = workspace_path / "data"
        data_dir.mkdir(exist_ok=True)
        for name, df in dataframes.items():
            df.to_parquet(data_dir / f"{name}.parquet")

        cmd = [
            "docker", "run", "--rm",
            "--network", "none",
            "--read-only",
            "--tmpfs", "/tmp:size=64m",
            "--memory=512m",
            "--cpus=1",
            "--pids-limit=64",
            "--ulimit", "cpu=10",
            "--user", "sandboxuser",
            "-v", f"{workspace}:/workspace:ro",
            settings.sandbox_image,
        ]
        try:
            proc = subprocess.run(
                cmd, capture_output=True, text=True, timeout=CONTAINER_RUN_TIMEOUT_SECONDS,
            )
            last_line = proc.stdout.strip().splitlines()[-1] if proc.stdout.strip() else "{}"
            return json.loads(last_line)
        except subprocess.TimeoutExpired:
            return {
                "ok": False,
                "error": "Sandbox execution timed out",
                "traceback": "Sandbox execution timed out",
            }
        except Exception as exc:  # noqa: BLE001 — malformed stdout, missing docker binary, etc.
            return {"ok": False, "error": str(exc), "traceback": str(exc)}
    finally:
        shutil.rmtree(workspace, ignore_errors=True)
