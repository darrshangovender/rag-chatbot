"""CLI: rebuild the chunk store from a directory of markdown files.

Usage:
    python -m api.ingest.cli --source ./demo/sample_kb --db ./data/index.sqlite
"""
from __future__ import annotations

import argparse
import time
from pathlib import Path

from .chunker import chunk_documents
from .embedder import embed_texts
from .loader import load_markdown_dir
from ..store.sqlite_store import SqliteStore


def main() -> None:
    ap = argparse.ArgumentParser(description="Build the RAG chunk store.")
    ap.add_argument("--source", required=True, help="Directory of .md files.")
    ap.add_argument("--db", default="./data/index.sqlite", help="SQLite output path.")
    ap.add_argument("--max-tokens", type=int, default=350)
    ap.add_argument("--overlap-tokens", type=int, default=60)
    args = ap.parse_args()

    t0 = time.perf_counter()
    docs = list(load_markdown_dir(args.source))
    print(f"loaded {len(docs)} docs from {args.source}")

    chunks = chunk_documents(
        docs, max_tokens=args.max_tokens, overlap_tokens=args.overlap_tokens
    )
    print(f"chunked into {len(chunks)} passages")

    print(f"embedding (this loads the model on first run)...")
    vecs = embed_texts([c.text for c in chunks])
    print(f"embeddings shape: {vecs.shape}")

    Path(args.db).parent.mkdir(parents=True, exist_ok=True)
    store = SqliteStore(args.db)
    store.reset()
    store.insert_chunks(chunks, vecs)
    store.set_meta("source_root", str(Path(args.source).resolve()))
    store.set_meta("indexed_at", str(time.time()))
    store.close()

    print(f"done in {time.perf_counter() - t0:.1f}s -> {args.db}")


if __name__ == "__main__":
    main()
