"""Local sentence-transformer embedder.

Defaults to `all-MiniLM-L6-v2` — small (~80 MB), CPU-friendly, 384 dims, and
good enough to demonstrate hybrid retrieval ranking behaviour. Swap the model
name via the `EMBED_MODEL` env var if you want a stronger encoder.

Why local instead of an API:
- Reference implementation should run offline after `make seed`.
- Eval numbers in the README are reproducible without an API key.
- Production swap: see `docs/swap-to-pgvector.md`.
"""
from __future__ import annotations

import os
from functools import lru_cache
from typing import Sequence

import numpy as np

_DEFAULT_MODEL = os.getenv("EMBED_MODEL", "sentence-transformers/all-MiniLM-L6-v2")


@lru_cache(maxsize=1)
def _model(model_name: str = _DEFAULT_MODEL):
    # Lazy import: sentence-transformers pulls in torch (~250 MB). We don't want
    # to pay that cost just to import the package.
    from sentence_transformers import SentenceTransformer

    return SentenceTransformer(model_name)


def embed_texts(
    texts: Sequence[str],
    *,
    batch_size: int = 32,
    normalize: bool = True,
    model_name: str | None = None,
) -> np.ndarray:
    """Embed a batch of texts. Returns float32 (N, D).

    `normalize=True` makes downstream cosine similarity a plain dot product,
    which the hybrid retriever takes advantage of.
    """
    if not texts:
        return np.zeros((0, embedding_dim()), dtype=np.float32)
    m = _model(model_name or _DEFAULT_MODEL)
    vecs = m.encode(
        list(texts),
        batch_size=batch_size,
        normalize_embeddings=normalize,
        convert_to_numpy=True,
        show_progress_bar=False,
    )
    return vecs.astype(np.float32, copy=False)


def embedding_dim(model_name: str | None = None) -> int:
    return _model(model_name or _DEFAULT_MODEL).get_sentence_embedding_dimension()
