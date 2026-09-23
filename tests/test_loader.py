"""Loader tests.

`source_path` is the citation key that ends up in user-visible answers, so the
tests below pin its shape (relative, POSIX separators) as hard as the content.
"""
from __future__ import annotations

from datetime import datetime

import pytest

from api.ingest.loader import _extract_title, load_markdown_dir


@pytest.fixture
def kb(tmp_path):
    """A small on-disk KB with nesting, a non-markdown file, and unicode."""
    (tmp_path / "guides").mkdir()
    (tmp_path / "guides" / "setup.md").write_text("# Setup\n\nInstall it.\n", encoding="utf-8")
    (tmp_path / "readme.md").write_text("No heading here.\n", encoding="utf-8")
    (tmp_path / "notes.txt").write_text("# Not markdown\n", encoding="utf-8")
    (tmp_path / "unicode.md").write_text("# Café ☕\n\nPrix: 5 €\n", encoding="utf-8")
    return tmp_path


def test_walks_recursively_and_skips_non_markdown(kb):
    docs = list(load_markdown_dir(kb))
    assert {d.source_path for d in docs} == {"guides/setup.md", "readme.md", "unicode.md"}


def test_source_path_is_relative_and_posix(kb):
    """Citations must be stable across machines and must not leak the user's home dir."""
    doc = next(d for d in load_markdown_dir(kb) if d.source_path.endswith("setup.md"))
    assert doc.source_path == "guides/setup.md"
    assert "\\" not in doc.source_path
    assert not doc.source_path.startswith(str(kb))


def test_title_comes_from_first_h1(kb):
    doc = next(d for d in load_markdown_dir(kb) if d.source_path == "guides/setup.md")
    assert doc.title == "Setup"


def test_title_falls_back_to_filename_stem(kb):
    doc = next(d for d in load_markdown_dir(kb) if d.source_path == "readme.md")
    assert doc.title == "readme"


def test_unicode_content_and_title_survive_utf8_roundtrip(kb):
    doc = next(d for d in load_markdown_dir(kb) if d.source_path == "unicode.md")
    assert doc.title == "Café ☕"
    assert "5 €" in doc.text


def test_ordering_is_deterministic(kb):
    """Chunk indices and any downstream golden files depend on a stable walk order."""
    assert [d.source_path for d in load_markdown_dir(kb)] == sorted(
        d.source_path for d in load_markdown_dir(kb)
    )


def test_last_modified_is_iso8601_utc(kb):
    doc = next(iter(load_markdown_dir(kb)))
    parsed = datetime.fromisoformat(doc.last_modified)
    assert parsed.utcoffset().total_seconds() == 0


def test_missing_directory_raises_filenotfound(tmp_path):
    with pytest.raises(FileNotFoundError, match="Source directory not found"):
        list(load_markdown_dir(tmp_path / "nope"))


def test_empty_directory_yields_nothing(tmp_path):
    assert list(load_markdown_dir(tmp_path)) == []


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("# Title", "Title"),
        ("\n\n# Title after blanks", "Title after blanks"),
        ("Preamble text\n# Later title", "Later title"),
        ("   # Indented", "Indented"),
        ("## Only an H2", "FALLBACK"),  # `# ` prefix required, so H2 is not a title
        ("#NoSpace", "FALLBACK"),  # `#Foo` is not a heading in CommonMark either
        ("", "FALLBACK"),
        ("# First\n# Second", "First"),
    ],
)
def test_extract_title_rules(text, expected):
    assert _extract_title(text, fallback="FALLBACK") == expected
