"""Heading-aware markdown chunker.

Uses `markdown-it-py` to walk the AST. The unit of chunking is a *section*: the
text under a heading at any level. Sections that exceed `max_tokens` are split
on paragraph boundaries with `overlap_tokens` of carry-over so a citation never
loses the surrounding sentence.

Token counting is approximate (whitespace-split). The point of token-aware
chunking here is not exact accounting — it's keeping chunks below the embedding
model's window and the LLM's per-passage budget.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Iterable

from markdown_it import MarkdownIt

from .loader import Document

_md = MarkdownIt("commonmark")


@dataclass
class Chunk:
    """A retrievable, embeddable unit of source content."""

    source_path: str
    section_path: str
    """Breadcrumb of headings, e.g. 'Billing > Refunds > Pro-rated refunds'."""

    text: str
    last_modified: str
    chunk_index: int
    extra: dict = field(default_factory=dict)


def _approx_tokens(text: str) -> int:
    # Whitespace tokens. Real tokenizers split sub-words, but for chunk-size
    # budgeting (not billing), this is within ~30% and avoids a tokenizer dep.
    return len(text.split())


def _split_sections(text: str) -> list[tuple[list[str], str]]:
    """Return [(heading_path, body_text)] for each heading-bounded section.

    Walks the markdown-it token stream and tracks heading depth so we get a
    proper breadcrumb (H1 > H2 > H3...). The body text excludes the heading line
    itself.
    """
    tokens = _md.parse(text)
    lines = text.splitlines()

    # heading boundaries: list of (start_line_idx, level, heading_text)
    headings: list[tuple[int, int, str]] = []
    i = 0
    while i < len(tokens):
        tok = tokens[i]
        if tok.type == "heading_open":
            level = int(tok.tag[1])  # h1 -> 1
            inline = tokens[i + 1] if i + 1 < len(tokens) else None
            heading_text = inline.content.strip() if inline else ""
            start_line = tok.map[0] if tok.map else 0
            headings.append((start_line, level, heading_text))
        i += 1

    if not headings:
        # Document without headings — single section.
        return [([], text.strip())]

    sections: list[tuple[list[str], str]] = []
    breadcrumb: list[tuple[int, str]] = []  # (level, text)

    # Prepend a virtual leading section if there's text before the first heading.
    first_line = headings[0][0]
    if first_line > 0:
        preamble = "\n".join(lines[:first_line]).strip()
        if preamble:
            sections.append(([], preamble))

    for idx, (start_line, level, heading_text) in enumerate(headings):
        # Pop deeper-or-equal headings off the breadcrumb stack.
        while breadcrumb and breadcrumb[-1][0] >= level:
            breadcrumb.pop()
        breadcrumb.append((level, heading_text))

        end_line = headings[idx + 1][0] if idx + 1 < len(headings) else len(lines)
        # Skip the heading line itself.
        body = "\n".join(lines[start_line + 1 : end_line]).strip()
        if body:
            path = [h for _, h in breadcrumb]
            sections.append((path, body))

    return sections


def _split_oversize(
    body: str, max_tokens: int, overlap_tokens: int
) -> list[str]:
    """Split a too-long section into paragraph-aligned windows with overlap.

    Never splits mid-paragraph. If a single paragraph is itself larger than
    `max_tokens`, it's emitted as one chunk (better an oversize chunk than a
    chunk that ends mid-sentence and tanks retrieval relevance).
    """
    paragraphs = [p.strip() for p in body.split("\n\n") if p.strip()]
    if not paragraphs:
        return []

    chunks: list[str] = []
    current: list[str] = []
    current_tokens = 0

    for para in paragraphs:
        ptokens = _approx_tokens(para)
        if current and current_tokens + ptokens > max_tokens:
            chunks.append("\n\n".join(current))
            # Build overlap: keep trailing paragraphs whose tokens fit in overlap budget.
            overlap: list[str] = []
            running = 0
            for back in reversed(current):
                t = _approx_tokens(back)
                if running + t > overlap_tokens:
                    break
                overlap.insert(0, back)
                running += t
            current = overlap[:]
            current_tokens = running
        current.append(para)
        current_tokens += ptokens

    if current:
        chunks.append("\n\n".join(current))
    return chunks


def chunk_document(
    doc: Document,
    *,
    max_tokens: int = 350,
    overlap_tokens: int = 60,
) -> list[Chunk]:
    """Chunk one Document into one or more retrievable Chunks."""
    out: list[Chunk] = []
    idx = 0
    for heading_path, body in _split_sections(doc.text):
        if _approx_tokens(body) <= max_tokens:
            pieces = [body]
        else:
            pieces = _split_oversize(body, max_tokens=max_tokens, overlap_tokens=overlap_tokens)
        section_path = " > ".join(heading_path) if heading_path else doc.title
        for piece in pieces:
            out.append(
                Chunk(
                    source_path=doc.source_path,
                    section_path=section_path,
                    text=piece,
                    last_modified=doc.last_modified,
                    chunk_index=idx,
                )
            )
            idx += 1
    return out


def chunk_documents(docs: Iterable[Document], **kw) -> list[Chunk]:
    out: list[Chunk] = []
    for d in docs:
        out.extend(chunk_document(d, **kw))
    return out
