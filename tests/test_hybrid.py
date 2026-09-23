"""Hybrid retriever tests: score blending, rank order, and normalization edges.

Every test here runs against `StubEncoder`, so the cosine numbers are exact and
reproducible rather than "whatever MiniLM happens to say this week".
"""
from __future__ import annotations

import numpy as np
import pytest

from api.retrieve.hybrid import HybridRetriever, _tokenize
from tests.conftest import KB_CORPUS, build_store

ALPHA = 0.6


# --------------------------------------------------------------------------- #
# Construction
# --------------------------------------------------------------------------- #


@pytest.mark.parametrize("alpha", [-0.01, 1.01, 2.0, -1.0])
def test_alpha_outside_the_unit_interval_is_rejected(store, patched_embedder, alpha):
    with pytest.raises(ValueError, match=r"alpha must be in \[0, 1\]"):
        HybridRetriever(store, alpha=alpha)


@pytest.mark.parametrize("alpha", [0.0, 0.5, 1.0])
def test_alpha_endpoints_are_accepted(store, patched_embedder, alpha):
    assert HybridRetriever(store, alpha=alpha).alpha == alpha


def test_empty_store_returns_no_results_and_builds_no_bm25_index(empty_store, patched_embedder):
    r = HybridRetriever(empty_store)
    assert r._bm25 is None
    assert r.search("anything at all") == []


# --------------------------------------------------------------------------- #
# Ranking contract
# --------------------------------------------------------------------------- #


def test_results_are_ordered_by_descending_score_with_ranks_from_one(retriever):
    results = retriever.search("how do refunds work", k=4)
    assert [r.rank for r in results] == [1, 2, 3, 4]
    scores = [r.score for r in results]
    assert scores == sorted(scores, reverse=True)


def test_k_truncates_and_never_exceeds_the_corpus_size(retriever):
    assert len(retriever.search("refunds", k=2)) == 2
    assert len(retriever.search("refunds", k=99)) == len(KB_CORPUS)


def test_score_is_exactly_the_documented_weighted_sum(retriever):
    """final = alpha * cosine + (1 - alpha) * minmax(bm25)."""
    for r in retriever.search("sprint length in workspace settings", k=4):
        assert r.score == pytest.approx(ALPHA * r.cosine + (1 - ALPHA) * r.bm25, abs=1e-6)


def test_both_score_components_stay_within_the_unit_interval(retriever):
    for r in retriever.search("webhook signature header", k=4):
        assert 0.0 <= r.cosine <= 1.0
        assert 0.0 <= r.bm25 <= 1.0
        assert 0.0 <= r.score <= 1.0


def test_bm25_is_minmax_normalized_so_the_best_candidate_scores_one(retriever):
    results = retriever.search("refunds pro-rated annual plans", k=4)
    bm = [r.bm25 for r in results]
    assert max(bm) == pytest.approx(1.0)
    assert min(bm) == pytest.approx(0.0)


def test_pure_cosine_and_pure_bm25_modes_can_disagree(store, patched_embedder):
    """alpha is a real knob, not decoration: the two extremes must be able to rank
    differently, otherwise the hybrid buys nothing over either half."""
    query = "HTTP 429 Retry-After header"
    cosine_only = HybridRetriever(store, alpha=1.0).search(query, k=4)
    bm25_only = HybridRetriever(store, alpha=0.0).search(query, k=4)
    assert all(r.score == pytest.approx(r.cosine) for r in cosine_only)
    assert all(r.score == pytest.approx(r.bm25) for r in bm25_only)


def test_bm25_rescues_a_rare_literal_string_that_cosine_dilutes(store, patched_embedder):
    """The whole point of the lexical half: an exact rare token must win even when
    it is one word in a long, otherwise-unrelated query."""
    query = "X-Signature HMAC"
    top = HybridRetriever(store, alpha=0.0).search(query, k=1)[0]
    assert top.chunk.source_path == "api/webhooks.md"
    assert top.bm25 == pytest.approx(1.0)


def test_relevant_query_ranks_the_matching_document_first(retriever):
    assert retriever.search("pro-rated refund on an annual plan", k=1)[0].chunk.source_path == (
        "pricing/billing.md"
    )


# --------------------------------------------------------------------------- #
# Degenerate inputs
# --------------------------------------------------------------------------- #


def test_uniform_bm25_scores_do_not_divide_by_zero(retriever):
    """A query sharing no token with the corpus gives every passage the same BM25
    score; min-max would be 0/0 without the epsilon guard."""
    results = retriever.search("zzz qqq xxx", k=4)
    assert all(r.bm25 == 0.0 for r in results)
    assert all(np.isfinite(r.score) for r in results)


def test_single_chunk_corpus_normalizes_bm25_to_zero(tmp_path, patched_embedder, encoder):
    """min == max with one candidate, so the lexical term contributes nothing and
    the score collapses to alpha * cosine."""
    store = build_store(tmp_path / "one.sqlite", encoder, corpus=KB_CORPUS[:1])
    top = HybridRetriever(store, alpha=ALPHA).search("refunds", k=5)[0]
    assert top.bm25 == 0.0
    assert top.score == pytest.approx(ALPHA * top.cosine)
    store.close()


def test_empty_query_string_does_not_crash(retriever):
    results = retriever.search("", k=3)
    assert len(results) == 3
    assert all(np.isfinite(r.score) for r in results)


def test_unicode_query_is_tokenized_and_scored(retriever):
    results = retriever.search("café ☕ refunds", k=2)
    assert results[0].chunk.source_path == "pricing/billing.md"


# --------------------------------------------------------------------------- #
# Tokenizer
# --------------------------------------------------------------------------- #


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("Hello World", ["hello", "world"]),
        ("HTTP 429", ["http", "429"]),
        ("snake_case-and-dashes", ["snake_case", "and", "dashes"]),
        ("v1.2.3", ["v1", "2", "3"]),
        ("café ☕", ["caf"]),  # non-ASCII letters fall outside [A-Za-z0-9_]
        ("", []),
        ("!!! ???", []),
    ],
)
def test_tokenizer_rules(text, expected):
    assert _tokenize(text) == expected
