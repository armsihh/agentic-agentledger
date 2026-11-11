"""retriever (gap 1): picks a small candidate window of events instead of handing the
Auditor the whole log. agentic-justification (b5): a simple keyword search over error-shaped
language, plus the tail of the conversation where decisive failures most often land, re-using
the existing search_log tool rather than re-implementing retrieval from scratch.
"""
from __future__ import annotations

from ..schema import Event, RunLog
from ..tools import search_log

_ERROR_QUERIES = ("error", "fail", "incorrect", "wrong", "exception", "mistake", "violat")
_TAIL_WINDOW = 4


def retrieve_candidates(run: RunLog, max_candidates: int = 12) -> list[Event]:
    """return a de-duplicated, step-ordered shortlist of events likely to matter."""
    seen: dict[str, Event] = {}

    for query in _ERROR_QUERIES:
        for e in search_log(run, query):
            seen[e.event_id] = e

    for e in run.events[-_TAIL_WINDOW:]:
        seen[e.event_id] = e

    if run.events:
        seen[run.events[0].event_id] = run.events[0]

    candidates = sorted(seen.values(), key=lambda e: e.step_index)
    if len(candidates) > max_candidates:
        # keep the most recent ones; recency matters most for attribution (see B5)
        candidates = candidates[-max_candidates:]
    return candidates
