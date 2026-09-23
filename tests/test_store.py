"""SqliteStore tests.

`load_all` feeds the retriever's cosine matrix directly, so the round-trip
fidelity of the float32 blobs matters as much as the SQL.
"""
from __future__ import annotations

import numpy as np
import pytest

from api.ingest.chunker import Chunk
from api.store.sqlite_store import SqliteStore
from tests.conftest import KB_CORPUS, make_chunks


def test_fresh_store_creates_schema_and_is_empty(empty_store):
    assert empty_store.count() == 0
    chunks, matrix = empty_store.load_all()
    assert chunks == []
    assert matrix.shape == (0, 0)
    assert matrix.dtype == np.float32


def test_insert_returns_row_ids_and_updates_count(tmp_path, encoder):
    store = SqliteStore(tmp_path / "i.sqlite")
    chunks = make_chunks()
    ids = store.insert_chunks(chunks, encoder([c.text for c in chunks]))
    assert len(ids) == len(chunks)
    assert len(set(ids)) == len(ids)
    assert store.count() == len(chunks)


def test_length_mismatch_is_rejected_before_any_write(tmp_path, encoder):
    """A partial insert would silently desync chunk ids from vectors."""
    store = SqliteStore(tmp_path / "i.sqlite")
    chunks = make_chunks()
    with pytest.raises(ValueError, match=r"4 vs 2"):
        store.insert_chunks(chunks, encoder([c.text for c in chunks[:2]]))
    assert store.count() == 0


def test_load_all_roundtrips_chunk_fields_in_insertion_order(store):
    chunks, _ = store.load_all()
    assert [c.source_path for c in chunks] == [row[0] for row in KB_CORPUS]
    assert [c.section_path for c in chunks] == [row[1] for row in KB_CORPUS]
    assert [c.text for c in chunks] == [row[2] for row in KB_CORPUS]
    assert [c.chunk_index for c in chunks] == list(range(len(KB_CORPUS)))


def test_load_all_returns_float32_matrix_matching_the_embeddings(store, encoder):
    _, matrix = store.load_all()
    expected = encoder([row[2] for row in KB_CORPUS])
    assert matrix.shape == expected.shape
    assert matrix.dtype == np.float32
    # Exact, not approximate: the blob is the raw float32 bytes.
    np.testing.assert_array_equal(matrix, expected)


def test_single_chunk_store_still_yields_a_two_dimensional_matrix(tmp_path, encoder):
    """`np.stack(...).reshape(n, dim)` must not collapse to 1-D for n == 1."""
    store = SqliteStore(tmp_path / "i.sqlite")
    chunks = make_chunks(KB_CORPUS[:1])
    store.insert_chunks(chunks, encoder([chunks[0].text]))
    _, matrix = store.load_all()
    assert matrix.ndim == 2
    assert matrix.shape[0] == 1


def test_reset_clears_chunks_embeddings_and_meta(store):
    store.set_meta("source_root", "/tmp/kb")
    store.reset()
    assert store.count() == 0
    assert store.get_meta("source_root") is None
    chunks, matrix = store.load_all()
    assert chunks == []
    assert matrix.shape == (0, 0)


def test_set_meta_upserts_rather_than_duplicating(store):
    store.set_meta("indexed_at", "1")
    store.set_meta("indexed_at", "2")
    assert store.get_meta("indexed_at") == "2"


def test_get_meta_returns_none_for_unknown_key(empty_store):
    assert empty_store.get_meta("never-set") is None


def test_unicode_text_survives_the_sqlite_roundtrip(tmp_path, encoder):
    store = SqliteStore(tmp_path / "i.sqlite")
    chunk = Chunk(
        source_path="i18n/café.md",
        section_path="Prix > Café ☕",
        text="Un café coûte 5 € — ça va.",
        last_modified="2024-01-01T00:00:00+00:00",
        chunk_index=0,
    )
    store.insert_chunks([chunk], encoder([chunk.text]))
    loaded, _ = store.load_all()
    assert loaded[0].text == chunk.text
    assert loaded[0].section_path == chunk.section_path
    assert loaded[0].source_path == chunk.source_path


def test_store_creates_missing_parent_directories(tmp_path):
    """`make seed` points at ./data/index.sqlite before ./data exists."""
    nested = tmp_path / "deep" / "nested" / "index.sqlite"
    SqliteStore(nested).close()
    assert nested.exists()


def test_extra_dict_is_persisted_but_not_returned_by_load_all(tmp_path, encoder):
    """Known asymmetry: `Chunk.extra` is written to extra_json, `StoredChunk` has no
    field for it, so it never comes back. Pinned so the write path is not mistaken
    for a working round-trip."""
    store = SqliteStore(tmp_path / "i.sqlite")
    chunk = make_chunks(KB_CORPUS[:1])[0]
    chunk.extra = {"owner": "billing-team"}
    store.insert_chunks([chunk], encoder([chunk.text]))
    stored = store.load_all()[0][0]
    assert not hasattr(stored, "extra")
    raw = store._conn.execute("SELECT extra_json FROM chunks").fetchone()[0]
    assert raw == '{"owner": "billing-team"}'
