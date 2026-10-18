"""Retrieval + fallback eval over the bundled synthetic knowledge base.

Measures two things, both on `demo/sample_kb` (23 synthetic documents):

1. **Retrieval**: for each in-scope question, is the document that holds the answer
   among the top-1 / top-5 retrieved chunks?
2. **Fallback**: at the configured confidence threshold, what share of out-of-scope
   questions is routed to a ticket, and what share of in-scope questions is wrongly
   routed to a ticket?

The questions are written by hand below, once, and are small (see the counts in the
output). The numbers describe this synthetic corpus and the local MiniLM encoder only;
they say nothing about a real help centre. The first run downloads the encoder
(about 90 MB); after that it runs offline.

Usage:
    python -m eval.run_eval
    python -m eval.run_eval --threshold 0.5
"""
from __future__ import annotations

import argparse
import sys
import tempfile
from pathlib import Path

from api.generate.fallback import DEFAULT_THRESHOLD
from api.ingest.chunker import chunk_documents
from api.ingest.embedder import embed_texts
from api.ingest.loader import load_markdown_dir
from api.retrieve.hybrid import HybridRetriever
from api.store.sqlite_store import SqliteStore

KB = Path(__file__).resolve().parent.parent / "demo" / "sample_kb"

# (question, document that contains the answer)
IN_SCOPE: list[tuple[str, str]] = [
    ("How do I revoke an API token?", "api/authentication.md"),
    ("How often should I rotate personal access tokens?", "api/authentication.md"),
    ("What are the API rate limits on each plan?", "api/rate-limits.md"),
    ("Which headers tell me how many requests I have left?", "api/rate-limits.md"),
    ("How do I verify a webhook signature?", "api/webhooks.md"),
    ("What happens when a webhook delivery fails?", "api/webhooks.md"),
    ("What does a 401 invalid_token error mean?", "api/errors.md"),
    ("How do I create a task through the API?", "api/tasks-endpoint.md"),
    ("How much does the Business plan cost per user?", "pricing/plans.md"),
    ("Can I get a refund on an annual plan?", "pricing/billing.md"),
    ("What happens when my free trial ends?", "pricing/trials.md"),
    ("How do I end a sprint and roll over unfinished tasks?", "features/sprints.md"),
    ("What are the available dashboard widgets?", "features/dashboards.md"),
    ("How do I set quiet hours for notifications?", "features/notifications.md"),
    ("How many times can an automation rule fire per day?", "features/automations.md"),
    ("What field types do custom fields support?", "features/custom-fields.md"),
    ("How do I disconnect the Slack integration?", "integrations/slack.md"),
    ("How are GitHub branches linked to tasks?", "integrations/github.md"),
    ("Which identity providers does SSO support?", "security/sso.md"),
    ("Which data residency regions are available?", "security/data-residency.md"),
    ("Which browsers are supported?", "getting-started/system-requirements.md"),
    ("How do I invite my team to a workspace?", "getting-started/quickstart.md"),
]

OUT_OF_SCOPE: list[str] = [
    "What is the capital of France?",
    "Who won the 1998 football world cup?",
    "Give me a recipe for chocolate cake.",
    "How do I change a flat tyre?",
    "What is the best programming language for beginners?",
    "Can you write me a poem about the sea?",
    "asdf qwerty zxcv",
    "What is the weather in Durban today?",
]


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--threshold", type=float, default=DEFAULT_THRESHOLD)
    ap.add_argument("--alpha", type=float, default=0.6)
    ap.add_argument("-v", "--verbose", action="store_true")
    args = ap.parse_args(argv)

    docs = list(load_markdown_dir(KB))
    chunks = chunk_documents(docs, max_tokens=350, overlap_tokens=60)
    vectors = embed_texts([c.text for c in chunks])

    with tempfile.TemporaryDirectory() as tmp:
        store = SqliteStore(Path(tmp) / "eval.sqlite")
        store.insert_chunks(chunks, vectors)
        retriever = HybridRetriever(store, alpha=args.alpha)

        hit1 = hit5 = false_fallback = 0
        in_scores: list[float] = []
        for question, expected in IN_SCOPE:
            passages = retriever.search(question, k=5)
            sources = [p.chunk.source_path for p in passages]
            top = passages[0].score
            in_scores.append(top)
            hit1 += sources[0] == expected
            hit5 += expected in sources
            false_fallback += top < args.threshold
            if args.verbose:
                mark = "MISS"
                if sources[0] == expected:
                    mark = "ok  "
                elif expected in sources:
                    mark = "top5"
                print(f"  [{mark}] {top:.3f} {question} -> {sources[0]}")

        refused = 0
        out_scores: list[float] = []
        for question in OUT_OF_SCOPE:
            top = retriever.search(question, k=5)[0].score
            out_scores.append(top)
            refused += top < args.threshold
            if args.verbose:
                print(f"  [{'tick' if top < args.threshold else 'ANSW'}] {top:.3f} {question}")
        store.close()

    n_in, n_out = len(IN_SCOPE), len(OUT_OF_SCOPE)
    print(f"corpus: {len(docs)} documents, {len(chunks)} chunks; alpha={args.alpha}")
    print(f"in-scope questions: {n_in}   out-of-scope questions: {n_out}")
    print(f"source hit@1: {hit1}/{n_in} ({100 * hit1 / n_in:.0f}%)")
    print(f"source hit@5: {hit5}/{n_in} ({100 * hit5 / n_in:.0f}%)")
    print(f"threshold {args.threshold}: out-of-scope sent to a ticket {refused}/{n_out}; "
          f"in-scope wrongly sent to a ticket {false_fallback}/{n_in}")
    print(f"top-score range: in-scope {min(in_scores):.3f}-{max(in_scores):.3f}; "
          f"out-of-scope {min(out_scores):.3f}-{max(out_scores):.3f}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
