"""FastAPI app exposing /ask over the hybrid retriever + citation guard."""
from __future__ import annotations

import os
import uuid
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field

from .generate.citation_guard import generate_answer
from .generate.fallback import (
    DEFAULT_THRESHOLD,
    FALLBACK_MESSAGE,
    check_confidence,
    open_ticket,
)
from .retrieve.hybrid import HybridRetriever
from .store.sqlite_store import SqliteStore


DB_PATH = os.getenv("RAG_DB_PATH", "./data/index.sqlite")
ALPHA = float(os.getenv("RAG_ALPHA", "0.6"))
THRESHOLD = float(os.getenv("RAG_CONFIDENCE_THRESHOLD", str(DEFAULT_THRESHOLD)))
TICKETS_PATH = os.getenv("RAG_TICKETS_PATH", "./data/tickets.jsonl")


class AskRequest(BaseModel):
    question: str = Field(min_length=1, max_length=1000)
    k: int = Field(default=5, ge=1, le=20)


class Citation(BaseModel):
    source_path: str
    section_path: str
    score: float


class AskResponse(BaseModel):
    request_id: str
    answer: str
    citations: list[Citation]
    fallback_triggered: bool
    top_score: float
    grounded: bool


@asynccontextmanager
async def lifespan(app: FastAPI):
    if not Path(DB_PATH).exists():
        raise RuntimeError(
            f"Index not found at {DB_PATH}. Run `make seed` first."
        )
    store = SqliteStore(DB_PATH)
    app.state.retriever = HybridRetriever(store, alpha=ALPHA)
    app.state.store = store
    yield
    store.close()


app = FastAPI(
    title="RAG chatbot reference",
    version="0.1.0",
    description="Hybrid-retrieval, citation-guarded RAG over a markdown KB.",
    lifespan=lifespan,
)


@app.get("/health")
async def health() -> dict:
    store: SqliteStore = app.state.store
    return {"status": "ok", "chunk_count": store.count(), "alpha": ALPHA}


@app.post("/ask", response_model=AskResponse)
async def ask(req: AskRequest) -> AskResponse:
    retriever: HybridRetriever = app.state.retriever
    request_id = str(uuid.uuid4())

    passages = retriever.search(req.question, k=req.k)
    decision = check_confidence(passages, threshold=THRESHOLD)

    if decision.triggered:
        open_ticket(
            question=req.question,
            top_score=decision.top_score,
            threshold=decision.threshold,
            tickets_path=TICKETS_PATH,
            request_id=request_id,
        )
        return AskResponse(
            request_id=request_id,
            answer=FALLBACK_MESSAGE,
            citations=[],
            fallback_triggered=True,
            top_score=decision.top_score,
            grounded=False,
        )

    try:
        answer = await generate_answer(req.question, passages)
    except KeyError as e:
        # ANTHROPIC_API_KEY missing when provider=anthropic
        raise HTTPException(500, f"LLM config error: missing env var {e}") from e

    cited_paths = set(answer.citations)
    citations = [
        Citation(
            source_path=p.chunk.source_path,
            section_path=p.chunk.section_path,
            score=p.score,
        )
        for p in passages
        if p.chunk.source_path in cited_paths
    ]

    return AskResponse(
        request_id=request_id,
        answer=answer.text,
        citations=citations,
        fallback_triggered=False,
        top_score=decision.top_score,
        grounded=answer.grounded,
    )
