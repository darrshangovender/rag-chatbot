"""Shared fixtures.

Everything here is deterministic and offline. The suite never loads
`sentence-transformers` (which would download a ~80 MB model on first use) and
never issues an HTTP request: `StubEncoder` stands in for the real embedder and
the Anthropic path is exercised through injected stubs.
"""
from __future__ import annotations

import hashlib
import re
from pathlib import Path

import numpy as np
import pytest

from api.ingest.chunker import Chunk
from api.ingest.loader import Document
from api.retrieve.hybrid import Retrieved
from api.store.sqlite_store import SqliteStore, StoredChunk

STUB_DIM = 64
"""Deliberately small. Big enough that hash collisions are rare across the tiny
test vocabularies, small enough that the matrices stay readable when debugging."""

_TOKEN_RE = re.compile(r"[A-Za-z0-9_]+")


class StubEncoder:
    """Deterministic hashing bag-of-words encoder with the real embedder's signature.

    Each token is hashed into one of `dim` buckets and counted, then the vector is
    L2-normalized. Two properties matter for the tests:

    * **Deterministic across processes.** Uses blake2b rather than the builtin
      `hash()`, which is salted per interpreter run (PYTHONHASHSEED).
    * **Non-negative components**, so cosine similarity always lands in [0, 1] —
      the same regime a real sentence-transformer operates in. This is what lets
      the hybrid-scoring and confidence-threshold tests assert real numbers.
    """

    def __init__(self, dim: int = STUB_DIM):
        self.dim = dim

    def __call__(
        self,
        texts,
        *,
        batch_size: int = 32,
        normalize: bool = True,
        model_name: str | None = None,
    ) -> np.ndarray:
        texts = list(texts)
        out = np.zeros((len(texts), self.dim), dtype=np.float32)
        for i, text in enumerate(texts):
            for token in _TOKEN_RE.findall(text.lower()):
                bucket = int(hashlib.blake2b(token.encode(), digest_size=8).hexdigest(), 16)
                out[i, bucket % self.dim] += 1.0
            if normalize:
                norm = float(np.linalg.norm(out[i]))
                if norm:
                    out[i] /= norm
        return out


@pytest.fixture
def encoder() -> StubEncoder:
    return StubEncoder()


@pytest.fixture
def patched_embedder(monkeypatch, encoder):
    """Swap the real embedder out of the retriever's namespace.

    `hybrid.py` does `from ..ingest.embedder import embed_texts`, so the name is
    bound in the *retriever's* module — patching `api.ingest.embedder.embed_texts`
    would have no effect.
    """
    monkeypatch.setattr("api.retrieve.hybrid.embed_texts", encoder)
    return encoder


# --------------------------------------------------------------------------- #
# Corpus fixtures
# --------------------------------------------------------------------------- #

KB_CORPUS: list[tuple[str, str, str]] = [
    (
        "pricing/billing.md",
        "Billing > Refunds",
        (
            "Refunds are pro-rated to the day on annual plans. Submit a refund request from "
            "the billing dashboard and our finance team reviews it within three business days. "
            "Refunds are returned to the original payment method."
        ),
    ),
    (
        "features/sprints.md",
        "Features > Sprints",
        (
            "Sprints are two-week iterations by default. You can change the sprint length in "
            "workspace settings. Unfinished tasks roll over into the next sprint automatically "
            "unless you archive them."
        ),
    ),
    (
        "api/rate-limits.md",
        "API > Rate limits",
        (
            "The API allows one hundred requests per minute per workspace token. Exceeding the "
            "limit returns HTTP 429 with a Retry-After header. Burst capacity is two hundred "
            "requests over a ten second window."
        ),
    ),
    (
        "api/webhooks.md",
        "API > Webhooks",
        (
            "Webhooks deliver task events to your endpoint over HTTPS. Each payload is signed "
            "with an HMAC SHA-256 signature in the X-Signature header. Failed deliveries retry "
            "with exponential backoff for up to twenty four hours."
        ),
    ),
]


def make_chunks(corpus=KB_CORPUS) -> list[Chunk]:
    return [
        Chunk(
            source_path=source,
            section_path=section,
            text=text,
            last_modified="2024-01-01T00:00:00+00:00",
            chunk_index=i,
        )
        for i, (source, section, text) in enumerate(corpus)
    ]


def build_store(path: Path, encoder: StubEncoder, corpus=KB_CORPUS) -> SqliteStore:
    """Seed a SqliteStore with stub embeddings — no model download."""
    store = SqliteStore(path)
    chunks = make_chunks(corpus)
    store.insert_chunks(chunks, encoder([c.text for c in chunks]))
    return store


@pytest.fixture
def store(tmp_path, encoder) -> SqliteStore:
    s = build_store(tmp_path / "index.sqlite", encoder)
    yield s
    s.close()


@pytest.fixture
def empty_store(tmp_path) -> SqliteStore:
    s = SqliteStore(tmp_path / "empty.sqlite")
    yield s
    s.close()


@pytest.fixture
def retriever(store, patched_embedder):
    from api.retrieve.hybrid import HybridRetriever

    return HybridRetriever(store, alpha=0.6)


# --------------------------------------------------------------------------- #
# Lightweight builders for unit tests that don't need a database
# --------------------------------------------------------------------------- #


def stored_chunk(
    text: str,
    *,
    id: int = 1,
    source_path: str = "docs/a.md",
    section_path: str = "A",
) -> StoredChunk:
    return StoredChunk(
        id=id,
        source_path=source_path,
        section_path=section_path,
        text=text,
        last_modified="2024-01-01T00:00:00+00:00",
        chunk_index=0,
    )


def retrieved(
    text: str,
    *,
    score: float = 0.9,
    source_path: str = "docs/a.md",
    section_path: str = "A",
    rank: int = 1,
) -> Retrieved:
    """A `Retrieved` with plausible components, for testing consumers of retrieval."""
    return Retrieved(
        chunk=stored_chunk(text, id=rank, source_path=source_path, section_path=section_path),
        score=score,
        cosine=score,
        bm25=score,
        rank=rank,
    )


def make_document(text: str, *, source_path: str = "a.md", title: str = "A") -> Document:
    return Document(
        source_path=source_path,
        title=title,
        text=text,
        last_modified="2024-01-01T00:00:00+00:00",
    )
