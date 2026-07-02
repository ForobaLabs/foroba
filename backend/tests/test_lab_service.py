import httpx
import pytest

import lab_service
import sandbox_docker
from sandbox_guard import DisallowedImportError


async def _collect(gen):
    return [event async for event in gen]


@pytest.mark.asyncio
async def test_run_lab_turn_happy_path(monkeypatch):
    monkeypatch.setattr(sandbox_docker, "is_docker_running", lambda: True)
    monkeypatch.setattr(
        lab_service, "_generate_code",
        lambda *a, **k: {"explanation": "computing", "code": "result_text = 'hi'"},
    )
    monkeypatch.setattr(lab_service, "check_imports", lambda code: None)
    monkeypatch.setattr(
        sandbox_docker, "run_sandbox",
        lambda code, dfs: {"ok": True, "text": "the answer is 42", "artifacts": []},
    )
    monkeypatch.setattr(lab_service, "_update_user_context", lambda *a, **k: "updated ctx")

    events = await _collect(lab_service.run_lab_turn("q", {}, [], ""))
    types = [e["type"] for e in events]
    assert "token" in types
    assert types[-1] == "done"
    assert events[-1]["context"] == "updated ctx"


@pytest.mark.asyncio
async def test_run_lab_turn_retries_on_disallowed_import(monkeypatch):
    monkeypatch.setattr(sandbox_docker, "is_docker_running", lambda: True)

    attempts = {"n": 0}

    def _check_imports(code):
        attempts["n"] += 1
        if attempts["n"] == 1:
            raise DisallowedImportError("os is not allowed")

    monkeypatch.setattr(
        lab_service, "_generate_code",
        lambda *a, **k: {"explanation": "computing", "code": "result_text = 'hi'"},
    )
    monkeypatch.setattr(lab_service, "check_imports", _check_imports)
    monkeypatch.setattr(
        sandbox_docker, "run_sandbox",
        lambda code, dfs: {"ok": True, "text": "ok", "artifacts": []},
    )
    monkeypatch.setattr(lab_service, "_update_user_context", lambda *a, **k: "ctx")

    events = await _collect(lab_service.run_lab_turn("q", {}, [], ""))
    assert events[-1]["type"] == "done"
    assert attempts["n"] == 2


@pytest.mark.asyncio
async def test_run_lab_turn_exhausts_retries_and_errors(monkeypatch):
    monkeypatch.setattr(sandbox_docker, "is_docker_running", lambda: True)
    monkeypatch.setattr(
        lab_service, "_generate_code",
        lambda *a, **k: {"explanation": "computing", "code": "1/0"},
    )
    monkeypatch.setattr(lab_service, "check_imports", lambda code: None)
    monkeypatch.setattr(
        sandbox_docker, "run_sandbox",
        lambda code, dfs: {"ok": False, "error": "ZeroDivisionError", "traceback": "..."},
    )

    events = await _collect(lab_service.run_lab_turn("q", {}, [], ""))
    assert events[-1]["type"] == "error"


@pytest.mark.asyncio
async def test_run_lab_turn_docker_not_running_and_fails_to_start(monkeypatch):
    monkeypatch.setattr(sandbox_docker, "is_docker_running", lambda: False)

    async def _ensure(*a, **k):
        return False
    monkeypatch.setattr(sandbox_docker, "ensure_docker_running", _ensure)

    called = {"n": 0}

    def _generate(*a, **k):
        called["n"] += 1
        return {"explanation": "", "code": ""}
    monkeypatch.setattr(lab_service, "_generate_code", _generate)

    events = await _collect(lab_service.run_lab_turn("q", {}, [], ""))
    types = [e["type"] for e in events]
    assert types == ["status", "error"]
    assert called["n"] == 0


@pytest.mark.asyncio
async def test_run_lab_turn_generate_code_exception_retries_then_succeeds(monkeypatch):
    monkeypatch.setattr(sandbox_docker, "is_docker_running", lambda: True)

    calls = {"n": 0}

    def _generate(*a, **k):
        calls["n"] += 1
        if calls["n"] == 1:
            raise httpx.ConnectError("connection refused")
        return {"explanation": "computing", "code": "result_text = 'hi'"}

    monkeypatch.setattr(lab_service, "_generate_code", _generate)
    monkeypatch.setattr(lab_service, "check_imports", lambda code: None)
    monkeypatch.setattr(
        sandbox_docker, "run_sandbox",
        lambda code, dfs: {"ok": True, "text": "ok", "artifacts": []},
    )
    monkeypatch.setattr(lab_service, "_update_user_context", lambda *a, **k: "ctx")

    events = await _collect(lab_service.run_lab_turn("q", {}, [], ""))
    assert events[-1]["type"] == "done"
    assert calls["n"] == 2
