"""Citation-guarded answer generation.

Two layers of defense against hallucination (see docs/prompt-design.md):

1. **Prompt contract.** The system prompt forbids any claim not grounded in
   the numbered context. The model is told to cite chunk numbers like `[1]`
   after every sentence.

2. **Post-processor.** Any sentence with no `[n]` citation is stripped before
   the response goes to the user.

The LLM call is pluggable. By default the guard runs in `extractive` mode —
no API key required — which composes an answer from the top-ranked passages
verbatim with citations. Set `LLM_PROVIDER=anthropic` and `ANTHROPIC_API_KEY`
to use Claude.
"""
from __future__ import annotations

import os
import re
from dataclasses import dataclass
from typing import Sequence

from ..retrieve.hybrid import Retrieved

SYSTEM_PROMPT = """You are a customer-support assistant for the Cumulus project-management tool.

Rules — these are not suggestions:
1. Answer ONLY from the numbered context passages below. Do not use outside knowledge.
2. After every sentence in your answer, cite the passage(s) it came from using \
the format [1], [2], etc. A sentence with no citation will be deleted.
3. If the context does not contain the answer, reply with exactly: \
"I don't have that information in my knowledge base."
4. Keep answers concise (2-5 sentences). Do not pad with restatements.
5. Never invent product names, prices, API endpoints, or version numbers."""


CITATION_RE = re.compile(r"\[(\d+)\]")
# Sentence splitter that respects citation markers (won't split on the period in `v1.2`).
SENTENCE_RE = re.compile(r"(?<=[.!?])\s+(?=[A-Z\"])")


@dataclass
class Answer:
    text: str
    """The post-processed answer with citation markers preserved."""

    citations: list[str]
    """source_path values for each unique [n] cited in the final text."""

    raw_text: str
    """The pre-strip LLM output, kept for debugging / eval."""

    grounded: bool
    """False if the post-processor stripped everything (model wandered)."""


def _build_context_block(passages: Sequence[Retrieved]) -> str:
    lines: list[str] = []
    for i, p in enumerate(passages, start=1):
        c = p.chunk
        lines.append(f"[{i}] source: {c.source_path} · section: {c.section_path}")
        lines.append(c.text.strip())
        lines.append("")
    return "\n".join(lines).rstrip()


def _strip_uncited_sentences(text: str, n_passages: int) -> tuple[str, list[int]]:
    """Drop every sentence that lacks a `[n]` marker with n in [1, n_passages].

    Returns (cleaned_text, list_of_cited_indices_1_based).
    """
    sentences = SENTENCE_RE.split(text.strip())
    kept: list[str] = []
    cited: set[int] = set()
    for sent in sentences:
        nums = [int(m) for m in CITATION_RE.findall(sent)]
        valid = [n for n in nums if 1 <= n <= n_passages]
        if valid:
            kept.append(sent.strip())
            cited.update(valid)
    return " ".join(kept), sorted(cited)


def _extractive_answer(question: str, passages: Sequence[Retrieved]) -> str:
    """Fallback when no LLM provider is configured.

    Strategy: take the first 1-2 sentences of each of the top 3 passages and
    tag them with [n]. Not pretty, not conversational, but it's grounded by
    construction and lets `make eval` run with no API key.
    """
    out: list[str] = []
    for i, p in enumerate(passages[:3], start=1):
        sents = SENTENCE_RE.split(p.chunk.text.strip())
        snippet = " ".join(sents[:2]).strip()
        if snippet:
            out.append(f"{snippet} [{i}]")
    return " ".join(out) if out else "I don't have that information in my knowledge base."


async def _anthropic_answer(question: str, context_block: str) -> str:
    """Call Claude. Requires ANTHROPIC_API_KEY."""
    import httpx

    api_key = os.environ["ANTHROPIC_API_KEY"]
    model = os.getenv("LLM_MODEL", "claude-3-5-haiku-latest")
    user_msg = f"Context passages:\n{context_block}\n\nQuestion: {question}"
    async with httpx.AsyncClient(timeout=30.0) as client:
        r = await client.post(
            "https://api.anthropic.com/v1/messages",
            headers={
                "x-api-key": api_key,
                "anthropic-version": "2023-06-01",
                "content-type": "application/json",
            },
            json={
                "model": model,
                "max_tokens": 512,
                "system": SYSTEM_PROMPT,
                "messages": [{"role": "user", "content": user_msg}],
            },
        )
        r.raise_for_status()
        data = r.json()
        return "".join(b.get("text", "") for b in data.get("content", [])).strip()


async def generate_answer(
    question: str,
    passages: Sequence[Retrieved],
) -> Answer:
    """Generate a citation-guarded answer over the retrieved passages."""
    if not passages:
        return Answer(
            text="I don't have that information in my knowledge base.",
            citations=[],
            raw_text="",
            grounded=False,
        )

    context_block = _build_context_block(passages)
    provider = os.getenv("LLM_PROVIDER", "extractive").lower()

    if provider == "anthropic":
        raw = await _anthropic_answer(question, context_block)
    else:
        raw = _extractive_answer(question, passages)

    cleaned, cited_idx = _strip_uncited_sentences(raw, n_passages=len(passages))
    grounded = bool(cleaned.strip())
    if not grounded:
        cleaned = "I don't have that information in my knowledge base."

    citations = [passages[i - 1].chunk.source_path for i in cited_idx]
    # de-dupe preserving order
    seen: set[str] = set()
    citations = [c for c in citations if not (c in seen or seen.add(c))]

    return Answer(text=cleaned, citations=citations, raw_text=raw, grounded=grounded)
