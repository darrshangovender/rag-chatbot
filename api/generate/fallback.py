"""Confidence-threshold fallback.

If the top retrieved chunk's score is below `threshold`, we don't trust the
retrieval and refuse to guess. Instead we:

1. Reply with the "opening a ticket" message.
2. Append a JSON line to `tickets.jsonl` so a human can follow up.

Threshold tuning: the default 0.45 is calibrated against the demo corpus +
golden questions in `eval/`. Re-tune on your own corpus before relying on it.
"""
from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Sequence

from ..retrieve.hybrid import Retrieved

DEFAULT_THRESHOLD = 0.45
FALLBACK_MESSAGE = (
    "I'm not confident I can answer that from our knowledge base. "
    "I've opened a ticket so a human can follow up."
)


@dataclass
class FallbackDecision:
    triggered: bool
    top_score: float
    threshold: float


def check_confidence(
    passages: Sequence[Retrieved],
    *,
    threshold: float = DEFAULT_THRESHOLD,
) -> FallbackDecision:
    top = passages[0].score if passages else 0.0
    return FallbackDecision(
        triggered=top < threshold,
        top_score=top,
        threshold=threshold,
    )


def open_ticket(
    *,
    question: str,
    top_score: float,
    threshold: float,
    tickets_path: str | Path = "data/tickets.jsonl",
    request_id: str | None = None,
) -> None:
    """Append a ticket row. Caller is responsible for actually paging a human."""
    p = Path(tickets_path)
    p.parent.mkdir(parents=True, exist_ok=True)
    row = {
        "ts": datetime.now(tz=timezone.utc).isoformat(),
        "request_id": request_id,
        "question": question,
        "top_score": top_score,
        "threshold": threshold,
        "reason": "below_confidence_threshold",
    }
    with p.open("a", encoding="utf-8") as f:
        f.write(json.dumps(row) + "\n")
