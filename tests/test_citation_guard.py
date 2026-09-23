"""Citation-guard tests.

The post-processor is the last line of defence against a hallucinating model, so
these tests care most about what it *deletes*. The LLM path is exercised through
an injected async stub — the suite never reaches the network and never needs
`ANTHROPIC_API_KEY`.
"""
from __future__ import annotations

import pytest

from api.generate.citation_guard import (
    SENTENCE_RE,
    Answer,
    _build_context_block,
    _extractive_answer,
    _strip_uncited_sentences,
    generate_answer,
)
from tests.conftest import retrieved

CANNED = "I don't have that information in my knowledge base."


class MockLLM:
    """Stands in for `_anthropic_answer`. Records the prompt it was handed."""

    def __init__(self, reply: str):
        self.reply = reply
        self.calls: list[tuple[str, str]] = []

    async def __call__(self, question: str, context_block: str) -> str:
        self.calls.append((question, context_block))
        return self.reply


@pytest.fixture
def use_mock_llm(monkeypatch):
    def _install(reply: str) -> MockLLM:
        mock = MockLLM(reply)
        monkeypatch.setenv("LLM_PROVIDER", "anthropic")
        monkeypatch.setattr("api.generate.citation_guard._anthropic_answer", mock)
        return mock

    return _install


@pytest.fixture(autouse=True)
def default_to_extractive(monkeypatch):
    """Never inherit the developer's shell config into a test run."""
    monkeypatch.delenv("LLM_PROVIDER", raising=False)
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)


# --------------------------------------------------------------------------- #
# Sentence stripping
# --------------------------------------------------------------------------- #


def test_uncited_sentence_is_deleted_and_cited_one_survives():
    text = "Refunds are pro-rated [1]. We also throw in a free hat."
    cleaned, cited = _strip_uncited_sentences(text, n_passages=2)
    assert cleaned == "Refunds are pro-rated [1]."
    assert "free hat" not in cleaned
    assert cited == [1]


def test_everything_uncited_leaves_an_empty_string():
    cleaned, cited = _strip_uncited_sentences("No citations at all. None here.", n_passages=3)
    assert cleaned == ""
    assert cited == []


@pytest.mark.parametrize("marker", ["[0]", "[4]", "[99]", "[-1]"])
def test_out_of_range_citations_do_not_count_as_grounding(marker):
    """A model that invents `[7]` when it was given three passages is hallucinating
    a source, which is exactly what the guard exists to catch."""
    cleaned, cited = _strip_uncited_sentences(f"Claim {marker}.", n_passages=3)
    assert cleaned == ""
    assert cited == []


def test_multiple_citations_in_one_sentence_are_all_recorded():
    _, cited = _strip_uncited_sentences("Both agree [2][1].", n_passages=3)
    assert cited == [1, 2]  # sorted, de-duplicated


def test_repeated_citation_is_reported_once():
    _, cited = _strip_uncited_sentences("A [1]. B [1]. C [1].", n_passages=2)
    assert cited == [1]


def test_mixed_valid_and_invalid_markers_keep_the_sentence():
    cleaned, cited = _strip_uncited_sentences("Partly grounded [1][9].", n_passages=3)
    assert cleaned == "Partly grounded [1][9]."
    assert cited == [1]


def test_version_numbers_do_not_split_a_sentence():
    """`SENTENCE_RE` only breaks before a capital or a quote, so `v1.2` survives."""
    text = "Upgrade to v1.2 first [1]."
    assert SENTENCE_RE.split(text) == [text]
    cleaned, _ = _strip_uncited_sentences(text, n_passages=1)
    assert cleaned == text


def test_sentence_boundary_requires_a_capital_or_quote():
    kept, _ = _strip_uncited_sentences("Rate limit is 100 rps [1]. see the docs.", n_passages=1)
    # No split happened, so the uncited tail rides along on the cited sentence.
    assert kept == "Rate limit is 100 rps [1]. see the docs."


def test_unicode_survives_stripping():
    cleaned, cited = _strip_uncited_sentences("Un café coûte 5 € [1].", n_passages=1)
    assert cleaned == "Un café coûte 5 € [1]."
    assert cited == [1]


def test_empty_input_is_handled():
    assert _strip_uncited_sentences("", n_passages=3) == ("", [])


# --------------------------------------------------------------------------- #
# Context block
# --------------------------------------------------------------------------- #


def test_context_block_numbers_passages_from_one_with_provenance():
    block = _build_context_block(
        [
            retrieved("First body.", source_path="a.md", section_path="A > One", rank=1),
            retrieved("Second body.", source_path="b.md", section_path="B > Two", rank=2),
        ]
    )
    assert "[1] source: a.md · section: A > One" in block
    assert "[2] source: b.md · section: B > Two" in block
    assert block.index("[1]") < block.index("[2]")
    assert "First body." in block and "Second body." in block


# --------------------------------------------------------------------------- #
# Extractive mode (the no-API-key default)
# --------------------------------------------------------------------------- #


def test_extractive_answer_is_grounded_by_construction():
    passages = [
        retrieved("Refunds are pro-rated. Ask finance.", source_path="a.md", rank=1),
        retrieved("Sprints are two weeks.", source_path="b.md", rank=2),
    ]
    text = _extractive_answer("q", passages)
    assert "[1]" in text and "[2]" in text


def test_extractive_answer_uses_at_most_the_top_three_passages():
    passages = [retrieved(f"Body {i}.", source_path=f"{i}.md", rank=i) for i in range(1, 6)]
    text = _extractive_answer("q", passages)
    assert "[3]" in text
    assert "[4]" not in text and "[5]" not in text


def test_extractive_answer_takes_only_the_first_two_sentences():
    passages = [retrieved("One. Two. Three. Four.", rank=1)]
    text = _extractive_answer("q", passages)
    assert text == "One. Two. [1]"


def test_extractive_answer_falls_back_when_every_passage_is_blank():
    passages = [retrieved("   ", rank=1), retrieved("", rank=2)]
    assert _extractive_answer("q", passages) == CANNED


# --------------------------------------------------------------------------- #
# generate_answer
# --------------------------------------------------------------------------- #


async def test_no_passages_refuses_without_calling_any_model():
    answer = await generate_answer("anything", [])
    assert answer == Answer(text=CANNED, citations=[], raw_text="", grounded=False)


async def test_extractive_path_returns_citations_for_the_passages_it_used():
    passages = [
        retrieved("Refunds are pro-rated.", source_path="pricing/billing.md", rank=1),
        retrieved("Sprints are two weeks.", source_path="features/sprints.md", rank=2),
    ]
    answer = await generate_answer("how do refunds work", passages)
    assert answer.grounded is True
    assert answer.citations == ["pricing/billing.md", "features/sprints.md"]


async def test_citations_are_deduplicated_preserving_passage_order():
    """Two chunks of the same file must not produce the same citation twice."""
    passages = [
        retrieved("Alpha body.", source_path="same.md", rank=1),
        retrieved("Beta body.", source_path="other.md", rank=2),
        retrieved("Gamma body.", source_path="same.md", rank=3),
    ]
    answer = await generate_answer("q", passages)
    assert answer.citations == ["same.md", "other.md"]


async def test_ungrounded_model_output_is_replaced_by_the_refusal(use_mock_llm):
    """The prompt contract failed; the post-processor must still hold the line."""
    mock = use_mock_llm("Cumulus costs $12 per seat and ships a mobile app.")
    passages = [retrieved("Refunds are pro-rated.", source_path="a.md", rank=1)]
    answer = await generate_answer("what does it cost", passages)

    assert answer.grounded is False
    assert answer.text == CANNED
    assert answer.citations == []
    assert answer.raw_text == mock.reply, "raw output must be retained for eval/debugging"


async def test_partially_grounded_model_output_keeps_only_cited_sentences(use_mock_llm):
    use_mock_llm("Refunds are pro-rated [1]. Cumulus also has a mobile app.")
    passages = [retrieved("Refunds are pro-rated.", source_path="a.md", rank=1)]
    answer = await generate_answer("q", passages)

    assert answer.text == "Refunds are pro-rated [1]."
    assert answer.grounded is True
    assert "mobile app" not in answer.text
    assert "mobile app" in answer.raw_text


async def test_llm_receives_the_numbered_context_block(use_mock_llm):
    mock = use_mock_llm("Grounded [1].")
    passages = [retrieved("Refunds are pro-rated.", source_path="pricing/billing.md", rank=1)]
    await generate_answer("how do refunds work", passages)

    question, context = mock.calls[0]
    assert question == "how do refunds work"
    assert "[1] source: pricing/billing.md" in context
    assert "Refunds are pro-rated." in context


async def test_provider_selection_is_case_insensitive(use_mock_llm, monkeypatch):
    mock = use_mock_llm("Grounded [1].")
    monkeypatch.setenv("LLM_PROVIDER", "ANTHROPIC")
    await generate_answer("q", [retrieved("Body.", rank=1)])
    assert len(mock.calls) == 1


async def test_unknown_provider_falls_back_to_extractive(monkeypatch):
    """Anything other than `anthropic` must degrade to the offline path rather than
    erroring — that is what keeps `make eval` runnable without a key."""
    monkeypatch.setenv("LLM_PROVIDER", "some-future-vendor")
    answer = await generate_answer("q", [retrieved("Refunds are pro-rated.", rank=1)])
    assert answer.grounded is True
    assert "[1]" in answer.text
