"""SQLite-backed chunk store.

Schema:
  chunks(id PK, source_path, section_path, text, last_modified, chunk_index)
  embeddings(chunk_id PK, dim, vec BLOB)  -- float32 little-endian

Why SQLite for a reference impl:
- Zero infra. `make seed && make run` works on a laptop with no Docker.
- The hybrid retriever loads all vectors into memory and computes cosine in
  numpy. For demo corpora (<10k chunks) this is faster than a vector index.
- Production swap to pgvector is documented in `docs/swap-to-pgvector.md`;
  the API surface (`Store.search_*`) is the seam.
"""
from __future__ import annotations

import json
import sqlite3
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable

import numpy as np

from ..ingest.chunker import Chunk

_SCHEMA = """
CREATE TABLE IF NOT EXISTS chunks (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    source_path   TEXT NOT NULL,
    section_path  TEXT NOT NULL,
    text          TEXT NOT NULL,
    last_modified TEXT NOT NULL,
    chunk_index   INTEGER NOT NULL,
    extra_json    TEXT NOT NULL DEFAULT '{}'
);
CREATE INDEX IF NOT EXISTS idx_chunks_source ON chunks(source_path);

CREATE TABLE IF NOT EXISTS embeddings (
    chunk_id INTEGER PRIMARY KEY REFERENCES chunks(id) ON DELETE CASCADE,
    dim      INTEGER NOT NULL,
    vec      BLOB NOT NULL
);

CREATE TABLE IF NOT EXISTS meta (
    key   TEXT PRIMARY KEY,
    value TEXT NOT NULL
);
"""


@dataclass
class StoredChunk:
    id: int
    source_path: str
    section_path: str
    text: str
    last_modified: str
    chunk_index: int


class SqliteStore:
    def __init__(self, path: str | Path):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._conn = sqlite3.connect(self.path, check_same_thread=False)
        self._conn.executescript(_SCHEMA)
        self._conn.commit()

    # ---- write path --------------------------------------------------------

    def reset(self) -> None:
        self._conn.executescript(
            "DELETE FROM embeddings; DELETE FROM chunks; DELETE FROM meta;"
        )
        self._conn.commit()

    def insert_chunks(self, chunks: Iterable[Chunk], embeddings: np.ndarray) -> list[int]:
        chunks_list = list(chunks)
        if len(chunks_list) != embeddings.shape[0]:
            raise ValueError(
                f"chunks/embeddings length mismatch: {len(chunks_list)} vs {embeddings.shape[0]}"
            )
        dim = int(embeddings.shape[1])
        ids: list[int] = []
        cur = self._conn.cursor()
        for chunk, vec in zip(chunks_list, embeddings):
            cur.execute(
                """INSERT INTO chunks
                       (source_path, section_path, text, last_modified, chunk_index, extra_json)
                   VALUES (?, ?, ?, ?, ?, ?)""",
                (
                    chunk.source_path,
                    chunk.section_path,
                    chunk.text,
                    chunk.last_modified,
                    chunk.chunk_index,
                    json.dumps(chunk.extra),
                ),
            )
            chunk_id = cur.lastrowid
            cur.execute(
                "INSERT INTO embeddings(chunk_id, dim, vec) VALUES (?, ?, ?)",
                (chunk_id, dim, vec.astype(np.float32).tobytes()),
            )
            ids.append(chunk_id)
        self._conn.commit()
        return ids

    def set_meta(self, key: str, value: str) -> None:
        self._conn.execute(
            "INSERT INTO meta(key, value) VALUES(?, ?) "
            "ON CONFLICT(key) DO UPDATE SET value=excluded.value",
            (key, value),
        )
        self._conn.commit()

    # ---- read path ---------------------------------------------------------

    def get_meta(self, key: str) -> str | None:
        row = self._conn.execute("SELECT value FROM meta WHERE key=?", (key,)).fetchone()
        return row[0] if row else None

    def count(self) -> int:
        return self._conn.execute("SELECT COUNT(*) FROM chunks").fetchone()[0]

    def load_all(self) -> tuple[list[StoredChunk], np.ndarray]:
        """Load every chunk + its embedding into memory.

        Fine for demo corpora. For production scale, push retrieval into
        Postgres+pgvector — see docs/swap-to-pgvector.md.
        """
        rows = self._conn.execute(
            """SELECT c.id, c.source_path, c.section_path, c.text,
                      c.last_modified, c.chunk_index, e.dim, e.vec
                 FROM chunks c JOIN embeddings e ON e.chunk_id = c.id
                ORDER BY c.id"""
        ).fetchall()
        if not rows:
            return [], np.zeros((0, 0), dtype=np.float32)
        chunks = [StoredChunk(*r[:6]) for r in rows]
        dim = rows[0][6]
        mat = np.stack(
            [np.frombuffer(r[7], dtype=np.float32) for r in rows]
        ).reshape(len(rows), dim)
        return chunks, mat

    def close(self) -> None:
        self._conn.close()
