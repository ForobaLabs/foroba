import base64
import io
import subprocess

import pandas as pd
from fastapi.testclient import TestClient

import main
import sandbox_docker
from config import settings

TOKEN = {"X-Sandbox-Token": "test-token"}


def test_health_endpoint():
    client = TestClient(main.app)
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_run_endpoint_happy_path(monkeypatch):
    monkeypatch.setattr(settings, "sandbox_runner_token", "test-token")
    def _fake_run(cmd, **kwargs):
        return subprocess.CompletedProcess(
            cmd, 0, stdout='{"ok": true, "text": "hello", "artifacts": []}\n',
        )
    monkeypatch.setattr(sandbox_docker.subprocess, "run", _fake_run)

    df = pd.DataFrame({"a": [1, 2, 3]})
    buf = io.BytesIO()
    df.to_parquet(buf)
    encoded = base64.b64encode(buf.getvalue()).decode("ascii")

    client = TestClient(main.app)
    response = client.post(
        "/run", json={"code": "result_text = 'hi'", "dataframes": {"df": encoded}}, headers=TOKEN,
    )
    assert response.status_code == 200
    assert response.json() == {"ok": True, "text": "hello", "artifacts": []}


def test_run_endpoint_no_dataframes(monkeypatch):
    monkeypatch.setattr(settings, "sandbox_runner_token", "test-token")
    def _fake_run(cmd, **kwargs):
        return subprocess.CompletedProcess(cmd, 0, stdout='{"ok": true, "text": "hi"}\n')
    monkeypatch.setattr(sandbox_docker.subprocess, "run", _fake_run)

    client = TestClient(main.app)
    response = client.post("/run", json={"code": "result_text = 'hi'", "dataframes": {}}, headers=TOKEN)
    assert response.status_code == 200
    assert response.json() == {"ok": True, "text": "hi"}
