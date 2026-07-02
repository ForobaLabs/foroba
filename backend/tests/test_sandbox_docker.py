import json
import subprocess
from unittest.mock import MagicMock

import pandas as pd

import sandbox_docker


def test_is_docker_running_true(monkeypatch):
    monkeypatch.setattr(subprocess, "run", lambda *a, **k: MagicMock())
    assert sandbox_docker.is_docker_running() is True


def test_is_docker_running_false_on_called_process_error(monkeypatch):
    def _raise(*a, **k):
        raise subprocess.CalledProcessError(1, "docker")
    monkeypatch.setattr(subprocess, "run", _raise)
    assert sandbox_docker.is_docker_running() is False


def test_is_docker_running_false_on_missing_binary(monkeypatch):
    def _raise(*a, **k):
        raise FileNotFoundError()
    monkeypatch.setattr(subprocess, "run", _raise)
    assert sandbox_docker.is_docker_running() is False


def test_run_sandbox_happy_path(monkeypatch):
    fake_result = {"ok": True, "text": "hello", "artifacts": []}

    def _fake_run(cmd, **kwargs):
        return MagicMock(stdout=json.dumps(fake_result) + "\n")
    monkeypatch.setattr(subprocess, "run", _fake_run)

    result = sandbox_docker.run_sandbox("result_text = 'hi'", {"df": pd.DataFrame({"a": [1]})})
    assert result == fake_result


def test_run_sandbox_handles_timeout(monkeypatch):
    def _raise(cmd, **kwargs):
        raise subprocess.TimeoutExpired(cmd="docker", timeout=15)
    monkeypatch.setattr(subprocess, "run", _raise)

    result = sandbox_docker.run_sandbox("code", {})
    assert result["ok"] is False
    assert "timed out" in result["error"].lower()


def test_run_sandbox_handles_malformed_stdout(monkeypatch):
    def _fake_run(cmd, **kwargs):
        return MagicMock(stdout="not json at all")
    monkeypatch.setattr(subprocess, "run", _fake_run)

    result = sandbox_docker.run_sandbox("code", {})
    assert result["ok"] is False
    assert "error" in result


def test_run_sandbox_handles_missing_docker_binary(monkeypatch):
    def _raise(cmd, **kwargs):
        raise FileNotFoundError("docker not found")
    monkeypatch.setattr(subprocess, "run", _raise)

    result = sandbox_docker.run_sandbox("code", {})
    assert result["ok"] is False
    assert "error" in result
