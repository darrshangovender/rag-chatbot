"""Markdown source loader.

Walks a directory of `.md` files and emits `Document` records with metadata
the downstream chunker, embedder, and citation guard need.
"""
from __future__ import annotations

import os
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterator


@dataclass
class Document:
    """A loaded source document, pre-chunking."""

    source_path: str
    """Repo-relative path. Used as the citation key."""

    title: str
    """First H1 if present, else the filename stem."""

    text: str

    last_modified: str
    """ISO-8601 UTC timestamp from the filesystem mtime."""

    extra: dict = field(default_factory=dict)


def _extract_title(text: str, fallback: str) -> str:
    for line in text.splitlines():
        line = line.strip()
        if line.startswith("# "):
            return line[2:].strip()
    return fallback


def load_markdown_dir(root: str | os.PathLike[str]) -> Iterator[Document]:
    """Yield a Document per `.md` file under `root` (recursive).

    Paths in `source_path` are returned relative to `root` for stable citation keys
    that don't leak the user's filesystem.
    """
    root_path = Path(root).resolve()
    if not root_path.exists():
        raise FileNotFoundError(f"Source directory not found: {root_path}")

    for path in sorted(root_path.rglob("*.md")):
        if not path.is_file():
            continue
        text = path.read_text(encoding="utf-8")
        rel = path.relative_to(root_path).as_posix()
        mtime = datetime.fromtimestamp(path.stat().st_mtime, tz=timezone.utc).isoformat()
        yield Document(
            source_path=rel,
            title=_extract_title(text, fallback=path.stem),
            text=text,
            last_modified=mtime,
        )
