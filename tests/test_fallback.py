"""Confidence-threshold fallback tests.

The headline case is `test_fallback_triggers_...` at the bottom of this file.
It is a regression test for a real bug: the affine cosine remap
`(cos + 1) / 2` in `retrieve/hybrid.py` put a floor of 0.5 under every
passage's cosine term. Combined with the min-max BM25 term — which always
awards 1.0 to *some* passage — the top score could never drop below
`alpha * 0.5 + (1 - alpha) * 1.0` = 0.70 at the default alpha=0.6. The 0.45
threshold sat below that floor, so the branch that opens a support ticket was
dead code for any query sharing even a single token with the corpus.
"""
from __future__ import annotations

import json
from datetime import datetime

import numpy as np
import pytest

from api.generate.fallback import DEFAULT_THRESHOLD, check_confidence, open_ticket
from api.retrieve.hybrid import HybridRetriever
from api.store.sqlite_store import SqliteStore
from tests.conftest import make_chunks, retrieved

ALPHA = 0.6


# --------------------------------------------------------------------------- #
# check_confidence
# --------------------------------------------------------------------------- #


def test_no_passages_scores_zero_and_triggers():
    decision = check_confidence([])
    assert decision.triggered is True
    assert decision.top_score == 0.0
    assert decision.threshold == DEFAULT_THRESHOLD


@pytest.mark.parametrize(
    ("top_score", "expected"),
    [
        (0.0, True),
        (0.44999, True),
        (0.45, False),  # boundary is `<`, so exactly-at-threshold is confident enough
        (0.45001, False),
        (1.0, False),
    ],
)
def test_threshold_boundary_is_strictly_less_than(top_score, expected):
    assert check_confidence([retrieved("x", score=top_score)]).triggered is expected


def test_decision_reads_the_first_passage_not_the_maximum():
    """The retriever already sorted by score; the fallback trusts that contract.
    If it ever stops sorting, this test is the thing that notices."""
    passages = [retrieved("a", score=0.10, rank=1), retrieved("b", score=0.99, rank=2)]
    decision = check_confidence(passages)
    assert decision.top_score == pytest.approx(0.10)
    assert decision.triggered is True


def test_custom_threshold_overrides_the_default():
    decision = check_confidence([retrieved("x", score=0.8)], threshold=0.9)
    assert decision.triggered is True
    assert decision.threshold == 0.9


# --------------------------------------------------------------------------- #
# open_ticket
# --------------------------------------------------------------------------- #


def test_ticket_creates_missing_parent_directories(tmp_path):
    path = tmp_path / "does" / "not" / "exist" / "tickets.jsonl"
    open_ticket(question="q", top_score=0.1, threshold=0.45, tickets_path=path)
    assert path.exists()


def test_ticket_row_carries_everything_a_human_needs(tmp_path):
    path = tmp_path / "tickets.jsonl"
    open_ticket(
        question="How do I export to Xero?",
        top_score=0.31,
        threshold=0.45,
        tickets_path=path,
        request_id="req-123",
    )
    row = json.loads(path.read_text(encoding="utf-8"))
    assert row["question"] == "How do I export to Xero?"
    assert row["top_score"] == pytest.approx(0.31)
    assert row["threshold"] == pytest.approx(0.45)
    assert row["request_id"] == "req-123"
    assert row["reason"] == "below_confidence_threshold"
    assert datetime.fromisoformat(row["ts"]).utcoffset().total_seconds() == 0


def test_tickets_append_one_json_object_per_line(tmp_path):
    path = tmp_path / "tickets.jsonl"
    for i in range(3):
        open_ticket(question=f"q{i}", top_score=0.1, threshold=0.45, tickets_path=path)
    lines = path.read_text(encoding="utf-8").splitlines()
    assert [json.loads(line)["question"] for line in lines] == ["q0", "q1", "q2"]


def test_ticket_survives_unicode_and_embedded_newlines(tmp_path):
    """A question is user input; it must not be able to corrupt the JSONL framing."""
    path = tmp_path / "tickets.jsonl"
    question = "Où est mon reçu ?\nLigne deux ☕"
    open_ticket(question=question, top_score=0.1, threshold=0.45, tickets_path=path)
    assert len(path.read_text(encoding="utf-8").splitlines()) == 1
    assert json.loads(path.read_text(encoding="utf-8"))["question"] == question


def test_missing_request_id_is_recorded_as_null(tmp_path):
    path = tmp_path / "tickets.jsonl"
    open_ticket(question="q", top_score=0.1, threshold=0.45, tickets_path=path)
    assert json.loads(path.read_text(encoding="utf-8"))["request_id"] is None


# --------------------------------------------------------------------------- #
# Regression: the fallback must be reachable end-to-end
# --------------------------------------------------------------------------- #

# One rare token per document. Only `zeppelin` is shared with the probe query,
# so BM25 has a real spread (one winner, two zeroes) rather than the flat,
# all-zero profile that a pure-gibberish query produces.
_TEXTS = [
    "Airships and the zeppelin mooring mast at Cardington.",
    "Sourdough hydration ratios for a cold retard.",
    "Narrowboat licencing on the Kennet and Avon.",
]
_COSINE_TO_QUERY = 0.05
"""What a real encoder returns for an off-topic query: near-orthogonal, not zero."""


@pytest.fixture
def controlled_retriever(tmp_path, monkeypatch):
    """Builds a retriever whose cosine values are dictated, not hashed.

    Chunk embeddings are the first three basis vectors, and the query vector is
    built to have cosine exactly `top_cosine` with chunk 0 and exactly 0.0 with
    the rest. That removes every source of numerical wobble — no hash collisions,
    no encoder drift — so the assertions below are about the *scoring formula*,
    not about what an encoder happened to produce that day.
    """
    stores: list[SqliteStore] = []

    def _build(top_cosine: float) -> HybridRetriever:
        dim = 8
        matrix = np.eye(3, dim, dtype=np.float32)

        query_vec = np.zeros((1, dim), dtype=np.float32)
        query_vec[0, 0] = top_cosine
        query_vec[0, dim - 1] = np.sqrt(1.0 - top_cosine**2)

        monkeypatch.setattr("api.retrieve.hybrid.embed_texts", lambda *a, **kw: query_vec)

        store = SqliteStore(tmp_path / f"controlled-{top_cosine}.sqlite")
        stores.append(store)
        corpus = [(f"kb/doc{i}.md", f"Doc {i}", text) for i, text in enumerate(_TEXTS)]
        store.insert_chunks(make_chunks(corpus), matrix)
        return HybridRetriever(store, alpha=ALPHA)

    yield _build
    for store in stores:
        store.close()


@pytest.fixture
def weak_match_retriever(controlled_retriever):
    return controlled_retriever(_COSINE_TO_QUERY)


def test_fallback_triggers_when_retrieval_is_weak(weak_match_retriever):
    """The regression test for the dead-branch bug.

    A single shared rare token gives one passage the full min-max BM25 point
    while the semantic match stays near zero. That is exactly the shape of an
    off-topic question, and it must open a ticket instead of being answered.
    """
    passages = weak_match_retriever.search("zeppelin", k=3)
    top = passages[0]

    assert top.bm25 == pytest.approx(1.0), "expected one lexical winner, not a flat profile"
    assert top.cosine == pytest.approx(_COSINE_TO_QUERY)

    expected = ALPHA * _COSINE_TO_QUERY + (1 - ALPHA) * 1.0  # 0.43
    assert top.score == pytest.approx(expected, abs=1e-6)

    decision = check_confidence(passages, threshold=DEFAULT_THRESHOLD)
    assert decision.triggered is True, (
        f"top score {decision.top_score:.4f} should be below the {DEFAULT_THRESHOLD} "
        "threshold — the ticket branch is unreachable again"
    )


def test_the_old_affine_remap_would_have_suppressed_that_ticket(weak_match_retriever):
    """Pins the specific arithmetic that was wrong.

    Recomputing the buggy `(cos + 1) / 2` remap over the same retrieval shows the
    top score landing at 0.715 — comfortably 'confident' about a passage with a
    0.05 cosine match. Keeping the counterfactual in the suite documents *why*
    the clip in `hybrid.py` must not be reverted to a rescale.
    """
    top = weak_match_retriever.search("zeppelin", k=3)[0]
    buggy_score = ALPHA * ((top.cosine + 1.0) / 2.0) + (1 - ALPHA) * top.bm25
    assert buggy_score > DEFAULT_THRESHOLD
    assert buggy_score == pytest.approx(0.715, abs=1e-6)


def test_orthogonal_passage_scores_zero_cosine_not_one_half(controlled_retriever):
    """The floor itself.

    A passage the query is exactly orthogonal to must contribute nothing. Under the
    old `(cos + 1) / 2` remap it scored exactly 0.5, handing out `alpha * 0.5` of
    unearned confidence to every passage in the corpus on every single query.
    """
    # Chunks 1 and 2 are orthogonal to the query vector by construction.
    results = {r.chunk.source_path: r for r in controlled_retriever(0.0).search("zeppelin", k=3)}
    for path in ("kb/doc1.md", "kb/doc2.md"):
        assert results[path].cosine == pytest.approx(0.0)
        assert results[path].score == pytest.approx(0.0)
    # Even the lexical winner keeps only its BM25 share — no free cosine mass.
    assert results["kb/doc0.md"].score == pytest.approx(1 - ALPHA)


def test_a_completely_unrelated_query_scores_near_zero(retriever):
    """Sanity check against the hashing stub rather than hand-built vectors: a
    query sharing no vocabulary with the corpus must land far below the threshold."""
    decision = check_confidence(retriever.search("zzz qqq xxx", k=4), threshold=DEFAULT_THRESHOLD)
    assert decision.triggered is True
    assert decision.top_score < 0.2


def test_a_genuinely_relevant_query_still_clears_the_threshold(retriever):
    """The fix must not make the fallback trigger-happy on good retrievals."""
    passages = retriever.search("refunds are pro-rated on annual plans", k=4)
    assert check_confidence(passages, threshold=DEFAULT_THRESHOLD).triggered is False
