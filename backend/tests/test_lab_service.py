import asyncio

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


@pytest.mark.asyncio
async def test_run_lab_turn_handles_null_code_from_llm(monkeypatch):
    """Regression: Ollama can return {"code": null} — must not crash ast.parse(None)."""
    monkeypatch.setattr(sandbox_docker, "is_docker_running", lambda: True)
    monkeypatch.setattr(
        lab_service, "_generate_code",
        lambda *a, **k: {"explanation": "no code needed", "code": None},
    )

    # Must not raise TypeError from ast.parse(None) — caught by the isinstance(code, str)
    # guard and fed back for retry instead of ever reaching check_imports/ast.parse.
    events = await _collect(lab_service.run_lab_turn("q", {}, [], ""))
    assert events[-1]["type"] == "error"


@pytest.mark.asyncio
async def test_run_lab_turn_handles_non_string_code_from_llm(monkeypatch):
    """Regression: Ollama can return {"code": [...]} or other non-string JSON types —
    generated.get("code") or "" only coerces falsy values, not wrong-typed truthy ones."""
    monkeypatch.setattr(sandbox_docker, "is_docker_running", lambda: True)
    monkeypatch.setattr(
        lab_service, "_generate_code",
        lambda *a, **k: {"explanation": "computing", "code": ["result_text = 'hi'"]},
    )

    # Must not raise TypeError from ast.parse(list) — caught by the isinstance(code, str) guard.
    events = await _collect(lab_service.run_lab_turn("q", {}, [], ""))
    assert events[-1]["type"] == "error"


@pytest.mark.asyncio
async def test_run_lab_turn_handles_markdown_fenced_code(monkeypatch):
    """Regression: LLM wrapping code in ```python fences must not crash ast.parse.

    Must raise SyntaxError caught internally, not propagate."""
    monkeypatch.setattr(sandbox_docker, "is_docker_running", lambda: True)
    monkeypatch.setattr(
        lab_service, "_generate_code",
        lambda *a, **k: {"explanation": "computing", "code": "```python\nresult_text = 'hi'\n```"},
    )

    # Must not raise SyntaxError from ast.parse — caught and fed back for retry instead.
    events = await _collect(lab_service.run_lab_turn("q", {}, [], ""))
    assert events[-1]["type"] == "error"


@pytest.mark.asyncio
async def test_run_lab_turn_passes_web_results_to_codegen(monkeypatch):
    monkeypatch.setattr(sandbox_docker, "is_docker_running", lambda: True)
    monkeypatch.setattr(
        sandbox_docker, "run_sandbox",
        lambda code, dfs: {"ok": True, "text": "done", "artifacts": []},
    )
    captured = {}

    def _fake_generate(*args, **kwargs):
        captured["web_results"] = args[5] if len(args) > 5 else kwargs.get("web_results")
        return {"explanation": "done", "code": "result_text = 'x'"}

    monkeypatch.setattr(lab_service, "_generate_code", _fake_generate)
    monkeypatch.setattr(lab_service, "check_imports", lambda code: None)
    monkeypatch.setattr(lab_service, "_update_user_context", lambda *a, **k: "ctx")

    await _collect(lab_service.run_lab_turn(
        "q", {}, [], "", web_results=[{"title": "T", "snippet": "S", "url": "U"}],
    ))

    assert captured["web_results"][0]["title"] == "T"


@pytest.mark.asyncio
async def test_run_lab_turn_reports_busy_when_sandbox_saturated(monkeypatch):
    """foroba#189: when the global sandbox concurrency cap is saturated, fail fast with
    a busy error instead of retrying codegen (retrying wouldn't help — it's a capacity
    issue, not a code issue)."""
    monkeypatch.setattr(sandbox_docker, "is_docker_running", lambda: True)
    monkeypatch.setattr(lab_service, "SANDBOX_QUEUE_WAIT_SECONDS", 0.05)

    generate_calls = {"n": 0}

    def _generate(*a, **k):
        generate_calls["n"] += 1
        return {"explanation": "computing", "code": "result_text = 'hi'"}

    monkeypatch.setattr(lab_service, "_generate_code", _generate)
    monkeypatch.setattr(lab_service, "check_imports", lambda code: None)

    # Swap in a size-1 semaphore and hold its only permit, so any acquire attempt
    # during the test always times out (saturated).
    test_semaphore = asyncio.Semaphore(1)
    await test_semaphore.acquire()
    monkeypatch.setattr(lab_service, "_sandbox_semaphore", test_semaphore)

    events = await _collect(lab_service.run_lab_turn("q", {}, [], ""))

    assert events[-1]["type"] == "error"
    assert "busy" in events[-1]["value"].lower()
    assert generate_calls["n"] == 1  # no retry burned on a capacity error
