"""Chunker tests.

Chunk boundaries decide what a citation can point at, so the interesting cases
are all boundaries: where a section starts, where an oversize split lands, and
how much text the overlap window carries forward.
"""
from __future__ import annotations

import pytest

from api.ingest.chunker import _approx_tokens, _split_oversize, _split_sections, chunk_document
from tests.conftest import make_document


def words(n: int, tag: str = "w") -> str:
    """A paragraph of exactly `n` whitespace tokens — `_approx_tokens` counts these."""
    return " ".join(f"{tag}{i}" for i in range(n))


# --------------------------------------------------------------------------- #
# Section splitting
# --------------------------------------------------------------------------- #


def test_document_without_headings_is_one_section_titled_by_document():
    doc = make_document("Just a paragraph.\n\nAnd another.", title="My Doc")
    chunks = chunk_document(doc)
    assert len(chunks) == 1
    assert chunks[0].section_path == "My Doc"
    assert chunks[0].text == "Just a paragraph.\n\nAnd another."


def test_heading_breadcrumb_nests_by_level():
    doc = make_document("# Billing\n\nTop.\n\n## Refunds\n\nMid.\n\n### Pro-rated\n\nDeep.\n")
    paths = [c.section_path for c in chunk_document(doc)]
    assert paths == ["Billing", "Billing > Refunds", "Billing > Refunds > Pro-rated"]


def test_sibling_heading_pops_the_breadcrumb():
    """A second H2 must replace the first, not nest under it."""
    doc = make_document("# Top\n\nT.\n\n## A\n\na.\n\n## B\n\nb.\n")
    paths = [c.section_path for c in chunk_document(doc)]
    assert paths == ["Top", "Top > A", "Top > B"]


def test_dedent_from_h3_back_to_h2_pops_both_levels():
    doc = make_document("# T\n\nt.\n\n## A\n\na.\n\n### A1\n\na1.\n\n## B\n\nb.\n")
    paths = [c.section_path for c in chunk_document(doc)]
    assert paths == ["T", "T > A", "T > A > A1", "T > B"]


def test_preamble_before_first_heading_becomes_its_own_section():
    doc = make_document("Intro sentence.\n\n# Heading\n\nBody.\n", title="Doc Title")
    chunks = chunk_document(doc)
    assert [c.text for c in chunks] == ["Intro sentence.", "Body."]
    # The preamble has no heading path, so it falls back to the document title.
    assert chunks[0].section_path == "Doc Title"
    assert chunks[1].section_path == "Heading"


def test_heading_with_empty_body_produces_no_chunk_but_still_nests():
    """A bare section header should not become an empty, unretrievable chunk."""
    doc = make_document("# Parent\n\n## Child\n\nOnly this has text.\n")
    chunks = chunk_document(doc)
    assert len(chunks) == 1
    assert chunks[0].section_path == "Parent > Child"


def test_heading_line_itself_is_excluded_from_body():
    doc = make_document("# Refund policy\n\nRefunds take 3 days.\n")
    assert chunk_document(doc)[0].text == "Refunds take 3 days."


def test_unicode_heading_survives_into_breadcrumb():
    doc = make_document("# Café ☕\n\n## Prix\n\n5 €\n")
    assert chunk_document(doc)[0].section_path == "Café ☕ > Prix"


def test_split_sections_on_empty_text_returns_one_empty_section():
    """Pinning a known wart: an empty document yields a single empty section.

    `chunk_document` therefore emits one zero-length chunk for an empty file,
    which would get embedded and indexed. Harmless on a curated KB, but pinned
    here so that changing it is a deliberate decision rather than a surprise.
    """
    assert _split_sections("") == [([], "")]
    assert [c.text for c in chunk_document(make_document("   \n\n  "))] == [""]


# --------------------------------------------------------------------------- #
# Oversize splitting and overlap
# --------------------------------------------------------------------------- #


def test_section_under_the_budget_is_never_split():
    doc = make_document(f"# H\n\n{words(10)}\n\n{words(10, 'x')}\n")
    assert len(chunk_document(doc, max_tokens=350)) == 1


def test_oversize_section_splits_on_paragraph_boundaries_only():
    """Chunks must never end mid-paragraph — that is what tanks retrieval relevance."""
    paragraphs = [words(6, "a"), words(6, "b"), words(6, "c")]
    doc = make_document("# H\n\n" + "\n\n".join(paragraphs))
    chunks = chunk_document(doc, max_tokens=10, overlap_tokens=0)
    assert [c.text for c in chunks] == paragraphs


def test_overlap_carries_the_previous_paragraph_forward():
    """Each split chunk should re-state enough context that a citation reads sensibly."""
    a, b, c = words(6, "a"), words(6, "b"), words(6, "c")
    pieces = _split_oversize(f"{a}\n\n{b}\n\n{c}", max_tokens=10, overlap_tokens=10)
    assert pieces == [a, f"{a}\n\n{b}", f"{b}\n\n{c}"]


def test_zero_overlap_budget_produces_disjoint_pieces():
    a, b, c = words(6, "a"), words(6, "b"), words(6, "c")
    pieces = _split_oversize(f"{a}\n\n{b}\n\n{c}", max_tokens=10, overlap_tokens=0)
    assert pieces == [a, b, c]


def test_single_paragraph_larger_than_budget_is_emitted_whole():
    """Better one oversize chunk than a chunk that stops mid-sentence."""
    big = words(500)
    pieces = _split_oversize(big, max_tokens=10, overlap_tokens=2)
    assert pieces == [big]


def test_split_oversize_on_blank_input_returns_nothing():
    assert _split_oversize("\n\n   \n\n", max_tokens=10, overlap_tokens=2) == []


# --------------------------------------------------------------------------- #
# Chunk metadata
# --------------------------------------------------------------------------- #


def test_chunk_index_increments_across_the_whole_document():
    doc = make_document(
        "# A\n\n" + "\n\n".join(words(6, t) for t in "xyz") + "\n\n## B\n\nshort body\n"
    )
    chunks = chunk_document(doc, max_tokens=10, overlap_tokens=0)
    assert [c.chunk_index for c in chunks] == list(range(len(chunks)))
    assert len(chunks) > 2  # the oversize section really did split


def test_chunks_inherit_document_provenance():
    doc = make_document("# H\n\nBody.\n", source_path="pricing/plans.md")
    chunk = chunk_document(doc)[0]
    assert chunk.source_path == "pricing/plans.md"
    assert chunk.last_modified == doc.last_modified


@pytest.mark.parametrize(
    ("text", "expected"),
    [("", 0), ("one", 1), ("one two", 2), ("  spaced   out  ", 2), ("line\nbreak", 2)],
)
def test_approx_token_count_is_whitespace_split(text, expected):
    assert _approx_tokens(text) == expected
