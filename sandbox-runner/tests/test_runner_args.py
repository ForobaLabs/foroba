import subprocess

from fastapi.testclient import TestClient

import main
import sandbox_docker
from config import settings
from sandbox_docker import build_docker_args


def test_docker_args_are_hardened():
    args = build_docker_args("run-1", "pfh-lab:py312", "/host/ws/run-1")
    for flag in ["--network", "none", "--read-only", "--cap-drop", "ALL",
                 "--security-opt", "no-new-privileges", "--pids-limit", "64",
                 "--memory", "512m", "--name", "pfh-sbx-run-1", "--rm"]:
        assert flag in args
    assert "--privileged" not in args
    assert args[-1] == "pfh-lab:py312"
    assert args[args.index("-v") + 1] == "/host/ws/run-1:/workspace:ro"


def test_timeout_kills_the_named_container(monkeypatch):
    calls: list[list[str]] = []

    def _fake_run(cmd, **kwargs):
        calls.append(cmd)
        if cmd[:2] == ["docker", "run"]:
            raise subprocess.TimeoutExpired(cmd, kwargs.get("timeout", 0))
        return subprocess.CompletedProcess(cmd, 0, stdout="")

    monkeypatch.setattr(sandbox_docker.subprocess, "run", _fake_run)
    result = sandbox_docker.run_sandbox("while True: pass", {})

    assert result["ok"] is False
    assert "timed out" in result["error"]
    name = calls[0][calls[0].index("--name") + 1]
    assert calls[1] == ["docker", "kill", name]


def test_run_rejects_missing_or_wrong_token(monkeypatch):
    monkeypatch.setattr(settings, "sandbox_runner_token", "s3cret-token")
    client = TestClient(main.app)
    body = {"code": "result_text = 'hi'", "dataframes": {}}
    assert client.post("/run", json=body).status_code == 403
    assert client.post("/run", json=body, headers={"X-Sandbox-Token": "nope"}).status_code == 403


def test_run_fails_closed_when_token_unset(monkeypatch):
    monkeypatch.setattr(settings, "sandbox_runner_token", "")
    client = TestClient(main.app)
    body = {"code": "result_text = 'hi'", "dataframes": {}}
    assert client.post("/run", json=body, headers={"X-Sandbox-Token": ""}).status_code == 403


def test_health_needs_no_token():
    assert TestClient(main.app).get("/health").status_code == 200
