"""The eval script must run end to end and its questions must match the KB.

The real encoder is replaced by the stub from conftest, so this checks the plumbing
(and that every expected document exists), not retrieval quality.
"""
from __future__ import annotations

from eval import run_eval
from tests.conftest import StubEncoder


def test_every_expected_source_exists_in_the_bundled_kb():
    for _, source in run_eval.IN_SCOPE:
        assert (run_eval.KB / source).is_file(), source


def test_eval_runs_offline_and_prints_a_summary(monkeypatch, capsys):
    encoder = StubEncoder()
    monkeypatch.setattr(run_eval, "embed_texts", encoder)
    monkeypatch.setattr("api.retrieve.hybrid.embed_texts", encoder)
    assert run_eval.main([]) == 0
    out = capsys.readouterr().out
    assert "source hit@1:" in out
    assert "source hit@5:" in out
    assert f"in-scope questions: {len(run_eval.IN_SCOPE)}" in out
