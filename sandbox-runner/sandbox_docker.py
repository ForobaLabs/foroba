"""Docker lifecycle for the Jeli Lab sandbox: container run, cleanup. Runs inside
sandbox-runner, the only service with Docker access (via DOCKER_HOST -> docker-socket-proxy).
See docs/superpowers/specs/2026-07-14-ti-b-item4-jeli-lab-sandbox-hardening-design.md.
"""
from __future__ import annotations

import json
import logging
import shutil
import subprocess
import uuid
from pathlib import Path
from typing import Any

import pandas as pd

from config import settings

logger = logging.getLogger(__name__)

CONTAINER_RUN_TIMEOUT_SECONDS = 15


def build_docker_args(run_id: str, image: str, host_workspace: str) -> list[str]:
    """The `docker run` argv for one sandboxed execution (Plan AU M-6). Pure, so the
    isolation flags are unit-tested: no network, read-only rootfs, no capabilities, no
    privilege escalation, bounded memory/pids/cpu, unprivileged user."""
    return [
        "docker", "run", "--rm", "--name", f"pfh-sbx-{run_id}",
        "--network", "none",
        "--read-only",
        "--tmpfs", "/tmp:rw,size=64m,noexec",
        "--memory", "512m",
        "--cpus", "1",
        "--pids-limit", "64",
        "--ulimit", "cpu=10",
        "--cap-drop", "ALL",
        "--security-opt", "no-new-privileges",
        "--user", "sandboxuser",
        "-v", f"{host_workspace}:/workspace:ro",
        image,
    ]


def _kill(run_id: str) -> None:
    try:
        subprocess.run(
            ["docker", "kill", f"pfh-sbx-{run_id}"], capture_output=True, timeout=10, check=False,
        )
    except Exception:  # best effort; the container may already be gone
        logger.warning("docker kill failed for pfh-sbx-%s", run_id, exc_info=True)


def run_sandbox(code: str, dataframes: dict[str, pd.DataFrame]) -> dict[str, Any]:
    """Run `code` against `dataframes` in an isolated container. Returns the parsed JSON result.

    sandbox-runner talks to the HOST's Docker daemon (via docker-socket-proxy), so the
    workspace must live under a bind mount shared with the host (`workspace_container_dir`
    inside this container / `workspace_host_dir` on the host) rather than an ephemeral
    tempdir private to this container — otherwise `docker run -v <path>:...` resolves
    against the daemon's (host's) filesystem and silently mounts an empty directory.
    """
    workspace_name = uuid.uuid4().hex
    workspace_path = Path(settings.workspace_container_dir) / workspace_name
    host_workspace = f"{settings.workspace_host_dir}/{workspace_name}"
    workspace_path.mkdir(parents=True, exist_ok=True)
    try:
        (workspace_path / "code.py").write_text(code)
        data_dir = workspace_path / "data"
        data_dir.mkdir(exist_ok=True)
        for name, df in dataframes.items():
            df.to_parquet(data_dir / f"{name}.parquet")

        cmd = build_docker_args(workspace_name, settings.sandbox_image, host_workspace)
        try:
            proc = subprocess.run(
                cmd, capture_output=True, text=True, timeout=CONTAINER_RUN_TIMEOUT_SECONDS, check=False,
            )
            last_line = proc.stdout.strip().splitlines()[-1] if proc.stdout.strip() else "{}"
            result = json.loads(last_line)
            if not result and proc.returncode != 0:
                return {"ok": False, "error": proc.stderr.strip(), "traceback": proc.stderr.strip()}
            return result
        except subprocess.TimeoutExpired:
            # `--rm` only fires once the container exits; the CLI timing out does not stop it.
            _kill(workspace_name)
            return {
                "ok": False,
                "error": "Sandbox execution timed out",
                "traceback": "Sandbox execution timed out",
            }
        except Exception as exc:  # noqa: BLE001 — malformed stdout, missing docker binary, etc.
            return {"ok": False, "error": str(exc), "traceback": str(exc)}
    finally:
        shutil.rmtree(workspace_path, ignore_errors=True)
