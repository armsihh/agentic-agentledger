"""Ingestion: parse a source log format into the normalised RunLog schema.

Phase 1 implements one format - a Who&When-style JSON record (run_id, an ordered
list of per-agent turns, and an optional ground-truth attribution). TRAIL
(OpenTelemetry spans) and MAST-Data ingestion are planned next (see B7/B8 in
the proposal) and follow the same `load_*_log -> RunLog` pattern.
"""
from __future__ import annotations

import json
from pathlib import Path

from .schema import Event, GroundTruth, RunLog, ToolCall


def load_whowhen_log(path: str | Path) -> RunLog:
    """Load a Who&When-style JSON log file into a normalised RunLog."""
    data = json.loads(Path(path).read_text(encoding="utf-8"))

    events = []
    for i, turn in enumerate(data["turns"]):
        tool_calls = [
            ToolCall(name=tc["name"], arguments=tc.get("arguments", {}), result=tc.get("result"))
            for tc in turn.get("tool_calls", [])
        ]
        events.append(
            Event(
                event_id=f"{data['run_id']}-{i}",
                run_id=data["run_id"],
                step_index=i,
                agent=turn["agent"],
                role=turn.get("role", "agent"),
                content=turn["content"],
                tool_calls=tool_calls,
                timestamp=turn.get("timestamp"),
            )
        )

    ground_truth = None
    if "ground_truth" in data:
        ground_truth = GroundTruth(
            responsible_agent=data["ground_truth"]["responsible_agent"],
            decisive_step=data["ground_truth"]["decisive_step"],
        )

    return RunLog(
        run_id=data["run_id"],
        source_format="whowhen",
        events=events,
        ground_truth=ground_truth,
    )


def load_logs_from_dir(directory: str | Path) -> list[RunLog]:
    """Load every *.json log in a directory (used by the eval harness)."""
    return [load_whowhen_log(p) for p in sorted(Path(directory).glob("*.json"))]
