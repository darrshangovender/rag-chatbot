# Changelog

All notable changes to this project are documented here. The format follows
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/).

## [0.1.1] - 2026-10-14

### Fixed
- Quick start: the Makefile had no `seed` or `run` target, so the README commands failed.
- Extractive answers: each passage's two-sentence snippet carried a single trailing `[n]`, so the
  citation guard deleted the first sentence and filed the next passage's first sentence under the
  wrong source. Every sentence now carries its own marker.
- Citation guard: a marker placed after the full stop (`Claim. [1] Uncited aside.`) glued two
  sentences into one, so the uncited sentence survived. Markers are moved before the punctuation
  before splitting.
- `/ask` returned an unhandled 500 when the model API failed; it now returns 502.
- Default Anthropic model changed from the superseded `claude-3-5-haiku-latest` to
  `claude-haiku-4-5`.
- `pyproject.toml` declared a wheel package (`eval`) that did not exist; dangling references to
  `docs/*.md` files that were never written were removed from docstrings.

### Added
- `eval/run_eval.py` (`make eval`): source hit@1 and hit@5 and fallback behaviour over 22 in-scope
  and 8 out-of-scope questions on the bundled synthetic KB.
- Tests for the three citation fixes, the 502 path and the eval script (138 to 144 tests).
- `CHANGELOG.md`, `demo/README.md` (data labelled synthetic), a lint gate in CI.

### Changed
- README rewritten to match the code: the confidence fallback is reachable (cosine is
  clipped, not remapped), the test suite exists, and the limitations list reflects what was measured.

## [0.1.0] - 2026-10-09

### Added
- Initial public reference implementation: heading-aware chunker, local MiniLM embeddings, hybrid
  dense + BM25 retrieval, SQLite store, citation guard, confidence fallback with a ticket log,
  FastAPI `/ask`, synthetic knowledge base, test suite.
