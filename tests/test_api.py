"""FastAPI surface tests.

`api.main` reads its configuration into module globals at import time, but every
handler dereferences those globals at call time — so `monkeypatch.setattr` on the
module is enough to point the app at a temp index without reimporting it.
"""
from __future__ import annotations

import json
import uuid
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from api import main as main_module
from tests.conftest import build_store

GOOD_QUESTION = "how do refunds work on annual plans"


@pytest.fixture
def configured_app(tmp_path, monkeypatch, encoder):
    """Point the app at a stub-embedded temp index and a temp ticket log."""
    db_path = tmp_path / "index.sqlite"
    build_store(db_path, encoder).close()

    monkeypatch.setattr("api.retrieve.hybrid.embed_texts", encoder)
    monkeypatch.setattr(main_module, "DB_PATH", str(db_path))
    monkeypatch.setattr(main_module, "TICKETS_PATH", str(tmp_path / "tickets.jsonl"))
    monkeypatch.setattr(main_module, "ALPHA", 0.6)
    monkeypatch.delenv("LLM_PROVIDER", raising=False)
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    return tmp_path


@pytest.fixture
def client(configured_app):
    with TestClient(main_module.app) as c:
        yield c


# --------------------------------------------------------------------------- #
# Startup
# --------------------------------------------------------------------------- #


def test_startup_refuses_to_serve_without_an_index(tmp_path, monkeypatch):
    """Serving an empty index would silently answer every question with the
    fallback; failing loudly at boot is the better failure."""
    monkeypatch.setattr(main_module, "DB_PATH", str(tmp_path / "missing.sqlite"))
    with pytest.raises(RuntimeError, match="Index not found"), TestClient(main_module.app):
        pass


def test_health_reports_index_size(client):
    body = client.get("/health").json()
    assert body == {"status": "ok", "chunk_count": 4, "alpha": 0.6}


# --------------------------------------------------------------------------- #
# /ask happy path
# --------------------------------------------------------------------------- #


def test_ask_answers_with_citations(client):
    body = client.post("/ask", json={"question": GOOD_QUESTION}).json()
    assert body["fallback_triggered"] is False
    assert body["grounded"] is True
    assert body["citations"], "a grounded answer must expose its sources"
    assert body["citations"][0]["source_path"] == "pricing/billing.md"
    assert uuid.UUID(body["request_id"])


def test_citations_are_restricted_to_sources_the_answer_actually_used(client):
    """The extractive path cites the top three passages, so a k=4 request must not
    return a citation for the fourth."""
    body = client.post("/ask", json={"question": GOOD_QUESTION, "k": 4}).json()
    assert 0 < len(body["citations"]) <= 3


def test_k_controls_how_many_passages_are_considered(client):
    body = client.post("/ask", json={"question": GOOD_QUESTION, "k": 1}).json()
    assert len(body["citations"]) == 1


def test_top_score_is_reported_even_on_the_happy_path(client):
    body = client.post("/ask", json={"question": GOOD_QUESTION}).json()
    assert body["top_score"] > main_module.THRESHOLD


def test_unicode_question_round_trips(client):
    resp = client.post("/ask", json={"question": "Comment obtenir un remboursement ☕ ?"})
    assert resp.status_code == 200


# --------------------------------------------------------------------------- #
# /ask fallback path
# --------------------------------------------------------------------------- #


def test_low_confidence_opens_a_ticket_and_refuses_to_answer(client, configured_app, monkeypatch):
    monkeypatch.setattr(main_module, "THRESHOLD", 0.99)
    body = client.post("/ask", json={"question": "who won the 1998 world cup"}).json()

    assert body["fallback_triggered"] is True
    assert body["grounded"] is False
    assert body["citations"] == []
    assert body["answer"] == main_module.FALLBACK_MESSAGE

    row = json.loads(Path(configured_app / "tickets.jsonl").read_text(encoding="utf-8"))
    assert row["question"] == "who won the 1998 world cup"
    assert row["request_id"] == body["request_id"]
    assert row["reason"] == "below_confidence_threshold"


def test_fallback_does_not_call_the_generator(client, monkeypatch):
    """No ticket-worthy question should ever cost an LLM call."""
    monkeypatch.setattr(main_module, "THRESHOLD", 0.99)

    async def boom(*a, **kw):  # pragma: no cover - must not run
        raise AssertionError("generate_answer was called on the fallback path")

    monkeypatch.setattr(main_module, "generate_answer", boom)
    assert client.post("/ask", json={"question": "anything"}).status_code == 200


# --------------------------------------------------------------------------- #
# Validation and error handling
# --------------------------------------------------------------------------- #


@pytest.mark.parametrize(
    "payload",
    [
        {"question": ""},  # min_length=1
        {"question": "x" * 1001},  # max_length=1000
        {"question": "ok", "k": 0},  # ge=1
        {"question": "ok", "k": 21},  # le=20
        {},  # question is required
    ],
)
def test_malformed_requests_are_rejected_with_422(client, payload):
    assert client.post("/ask", json=payload).status_code == 422


def test_missing_api_key_surfaces_as_a_config_error_not_a_crash(client, monkeypatch):
    monkeypatch.setenv("LLM_PROVIDER", "anthropic")
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    resp = client.post("/ask", json={"question": GOOD_QUESTION})
    assert resp.status_code == 500
    assert "ANTHROPIC_API_KEY" in resp.json()["detail"]


def test_each_request_gets_a_distinct_id(client):
    ids = {
        client.post("/ask", json={"question": GOOD_QUESTION}).json()["request_id"]
        for _ in range(3)
    }
    assert len(ids) == 3
