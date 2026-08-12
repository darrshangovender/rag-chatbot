"""Hybrid retriever: cosine similarity + BM25.

Score:  final = alpha * cosine + (1 - alpha) * minmax(bm25)
cosine in [0, 1] (embeddings are L2-normalized, then clipped from [-1, 1]).
bm25 is min-max normalized over the current query's candidate set.

Why both:
- Cosine wins on paraphrase / semantic similarity.
- BM25 wins on rare strings (model numbers, error codes, API method names).
- Min-max-normalizing BM25 *per query* keeps the weighted sum sane when one
  query has tiny absolute BM25 scores and another has huge ones.
"""
from __future__ import annotations

import re
from dataclasses import dataclass

import numpy as np
from rank_bm25 import BM25Okapi

from ..ingest.embedder import embed_texts
from ..store.sqlite_store import SqliteStore, StoredChunk

_TOKEN_RE = re.compile(r"[A-Za-z0-9_]+")


def _tokenize(text: str) -> list[str]:
    return [t.lower() for t in _TOKEN_RE.findall(text)]


@dataclass
class Retrieved:
    chunk: StoredChunk
    score: float
    cosine: float
    bm25: float
    rank: int


class HybridRetriever:
    """In-memory hybrid retriever over a `SqliteStore`.

    Loads all chunks + embeddings once at construction; rebuild the retriever
    after re-indexing. For a reference impl this beats lazy-loading on every
    query — the demo corpus fits in <50 MB of RAM.
    """

    def __init__(self, store: SqliteStore, *, alpha: float = 0.6):
        if not 0.0 <= alpha <= 1.0:
            raise ValueError(f"alpha must be in [0, 1], got {alpha}")
        self.alpha = alpha
        self.store = store
        self.chunks, self.matrix = store.load_all()
        if self.chunks:
            self._bm25 = BM25Okapi([_tokenize(c.text) for c in self.chunks])
        else:
            self._bm25 = None

    def search(self, query: str, *, k: int = 5) -> list[Retrieved]:
        if not self.chunks:
            return []

        # --- cosine ---
        qvec = embed_texts([query], normalize=True)[0]
        cos = self.matrix @ qvec  # (N,) since both sides normalized
        # numerical clip — embeddings are normalized so this should already be in [-1, 1]
        cos = np.clip(cos, -1.0, 1.0)
        # remap to [0, 1] so it composes with the [0, 1] BM25 score
        cos_norm = (cos + 1.0) / 2.0

        # --- BM25 ---
        bm = np.asarray(self._bm25.get_scores(_tokenize(query)), dtype=np.float32)
        bmin, bmax = float(bm.min()), float(bm.max())
        if bmax - bmin < 1e-9:
            bm_norm = np.zeros_like(bm)
        else:
            bm_norm = (bm - bmin) / (bmax - bmin)

        final = self.alpha * cos_norm + (1.0 - self.alpha) * bm_norm
        top_idx = np.argsort(-final)[:k]

        return [
            Retrieved(
                chunk=self.chunks[i],
                score=float(final[i]),
                cosine=float(cos_norm[i]),
                bm25=float(bm_norm[i]),
                rank=rank,
            )
            for rank, i in enumerate(top_idx, start=1)
        ]
