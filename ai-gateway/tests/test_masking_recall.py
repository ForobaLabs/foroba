"""PII recall gate: synthetic multilingual corpus (IT/FR/EN) must be >= 99% masked.

Corpus is generated deterministically by tests/fixtures/gen_pii_corpus.py.
"""
import json
import re
from collections import defaultdict
from pathlib import Path

import httpx
import pytest
import respx

import consent
import db
import prefs
import usage
from masking import engine

CORPUS = Path(__file__).parent / "fixtures" / "pii_corpus.jsonl"
ROWS = [json.loads(line) for line in CORPUS.read_text().splitlines() if line.strip()]
CF_URL = "https://api.cloudflare.com/client/v4/accounts/acc1/ai/v1/chat/completions"


def _norm(s: str) -> str:
    return re.sub(r"[\s.\-]", "", s)


def _leaks(masked: str, pii: list[str]) -> list[str]:
    flat = _norm(masked)
    return [p for p in pii if p in masked or _norm(p) in flat]


def test_corpus_shape():
    assert len(ROWS) >= 200
    assert {r["cat"] for r in ROWS} >= {
        "iban", "card", "cf", "nir", "email", "phone", "address", "person", "account",
    }


def test_masking_recall_ge_99():
    total = missed = 0
    per_cat = defaultdict(lambda: [0, 0])
    failures = []
    for row in ROWS:
        masked, _ = engine.mask(row["text"], engine.KnownEntities() if hasattr(engine, "KnownEntities") else None)
        for p in row["pii"]:
            total += 1
            per_cat[row["cat"]][1] += 1
            if _leaks(masked, [p]):
                missed += 1
                per_cat[row["cat"]][0] += 1
                failures.append((row["cat"], p))
    recall = 1 - missed / total
    assert recall >= 0.99, f"recall {recall:.3f}; misses by cat {dict(per_cat)}; {failures[:10]}"


def test_no_masking_error_on_corpus():
    for row in ROWS:
        engine.mask(row["text"], engine.KnownEntities() if hasattr(engine, "KnownEntities") else None)


@pytest.fixture(autouse=True)
def cloud_env(monkeypatch):
    for k, v in {
        "AI_CLOUD_ENABLED": "true",
        "CF_ACCOUNT_ID": "acc1",
        "CF_API_TOKEN": "cf-SECRET-token",
        "AI_TEST_ALLOWLIST": "",
    }.items():
        monkeypatch.setenv(k, v)


@respx.mock
def test_provider_request_contains_no_corpus_pii(api):
    sample = [r for i, r in enumerate(ROWS) if i % 5 == 0]
    conn = db.connect()
    for uid in range(100, 100 + len(sample)):  # one user per row: no rate-limit coupling
        consent.record(conn, uid, "cloudflare", "accept", None)
        prefs.put(conn, uid, "pazuru", "chat", "cloud", None)
    conn.close()
    route = respx.post(CF_URL).mock(
        return_value=httpx.Response(
            200,
            json={
                "model": "m",
                "choices": [{"message": {"role": "assistant", "content": "ok"}}],
                "usage": {"neurons": 1},
            },
        )
    )
    for uid, row in zip(range(100, 100 + len(sample)), sample):
        res = api(
            "POST",
            "/v1/chat",
            user=uid,
            tier="premium",
            json={
                "app": "pazuru", "feature": "chat", "task": "chat",
                "messages": [{"role": "user", "content": row["text"]}],
            },
        )
        assert res.status_code == 200 and res.json()["route"] == "remote"
    assert route.call_count == len(sample)
    for call, row in zip(route.calls, sample):
        sent = json.dumps(json.loads(call.request.content), ensure_ascii=False)
        assert not _leaks(sent, row["pii"]), (row["cat"], row["text"])
