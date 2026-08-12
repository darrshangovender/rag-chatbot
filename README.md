# RAG Customer-Support Chatbot

> Retrieval-augmented chatbot over a client knowledge base. Document chunking, embedding pipeline, pgvector storage, semantic retrieval, citation-aware LLM responses. Deflects repetitive support tickets and reduces average handling time.

**Stack:** Python · LangChain · pgvector (PostgreSQL) · OpenAI · FastAPI · Next.js
**Status:** Production for one client; engine reusable

---

## What it does

1. **Ingests** a client knowledge base (Notion exports, PDF manuals, help-centre HTML).
2. **Chunks and embeds** content with overlap-aware splitting that respects headings.
3. **Stores** chunks + embeddings + metadata (source URL, last-modified, section path) in pgvector.
4. **Retrieves** top-k passages per user question with a **hybrid score** (cosine similarity + BM25 keyword score).
5. **Generates** an answer that cites its sources inline and links back to the original document.
6. **Falls back** gracefully — if retrieval scores are below threshold, it says "I don't know" and creates a support ticket instead of hallucinating.

## Why a hybrid retriever

Pure embedding retrieval is great at semantic similarity but loses on rare strings (model numbers, error codes). Pure BM25 misses paraphrases. Combined, you get the best of both.

```python
# Simplified scoring (per chunk)
final_score = α * cosine_similarity + (1 - α) * normalize(bm25_score)
# α tuned per-client on a small labelled set
```

## Why citations are non-negotiable

The biggest risk in production RAG is plausible nonsense. Two layers of defence:

1. **Cite or shut up.** The system prompt forbids stating any fact not in the retrieved context. The model is instructed to cite the chunk ID for each claim; the post-processor strips claims with no citation.
2. **Confidence threshold.** If the top retrieved chunk's score is below threshold, the bot replies "I'm not confident on this — opening a ticket" rather than guessing.

## Architecture

```
                    ┌──────────────┐
                    │ Knowledge    │
                    │ base sources │
                    └──────┬───────┘
                           │ ingest
                           ▼
                    ┌──────────────────────┐
                    │ Chunker (heading-aware)│
                    └──────┬───────────────┘
                           ▼
                    ┌──────────────────────┐
                    │ Embedding worker     │
                    └──────┬───────────────┘
                           ▼
                    ┌──────────────────────┐
                    │ pgvector + BM25 idx  │
                    └──────┬───────────────┘
User question ─────▶ Hybrid retriever
                           │
                           ▼
                    ┌──────────────────────┐
                    │ LLM with citation    │
                    │ guard + threshold    │
                    └──────────────────────┘
```

## Repo structure

```
.
├── api/
│   ├── main.py
│   ├── ingest/         # Source loaders + chunker
│   ├── retrieve/       # Hybrid scorer
│   ├── generate/       # Citation-guarded LLM call
│   └── eval/           # Faithfulness + answer-relevance metrics
├── web/                # Embeddable chat widget (Next.js)
├── infra/
│   └── docker/
└── docs/
    └── prompt-design.md
```

## Evals

Three metrics, run on every prompt or chunker change:

| Metric | What it measures | Target |
|---|---|---|
| **Faithfulness** | Are answer claims supported by retrieved context? | > 0.95 |
| **Answer relevance** | Does the answer address the question? | > 0.90 |
| **Retrieval recall@5** | Is the gold passage in top-5? | > 0.85 |

Implemented via LangChain's `ragas` framework against a labelled set of 80 client-specific questions.

## Production results (one client)

- Reduced average first-response time on Tier 1 tickets from minutes to seconds.
- Deflected a meaningful share of repetitive tickets (numbers under NDA but material to the cost case).
- Zero hallucination incidents reported in the first 90 days post-launch.

## Local setup

```bash
docker compose up -d
uv sync
uv run python -m api.ingest.cli --source ./sample_kb
uv run uvicorn api.main:app --reload
```

## Author

Darrshan Govender · Founder, [Agulhas Code](https://agulhascode.co.za)
