"""parse a source log format into the normalised RunLog schema."""
from __future__ import annotations

import json
from pathlib import Path

from .schema import Event, GroundTruth, RunLog, ToolCall


def load_whowhen_log(path: str | Path) -> RunLog:
    """load a synthetic who&when-style json log into a RunLog."""
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
    """load every *.json log in a directory."""
    return [load_whowhen_log(p) for p in sorted(Path(directory).glob("*.json"))]


def load_whowhen_release_record(path: str | Path, is_handcrafted: bool) -> RunLog:
    """parse one record from the real who&when release (base paper [1]) into a RunLog.

    agent name comes from "role" for hand-crafted records and "name" for
    algorithm-generated ones, matching the reference repo's own convention.
    """
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    run_id = data.get("question_ID", Path(path).stem)
    agent_key = "role" if is_handcrafted else "name"

    events = []
    for i, turn in enumerate(data.get("history", [])):
        agent = turn.get(agent_key) or turn.get("role") or "unknown"
        events.append(
            Event(
                event_id=f"{run_id}-{i}",
                run_id=run_id,
                step_index=i,
                agent=agent,
                role="agent",
                content=turn.get("content", ""),
                tool_calls=[],
            )
        )

    ground_truth = None
    if data.get("mistake_agent") is not None and data.get("mistake_step") is not None:
        ground_truth = GroundTruth(
            responsible_agent=data["mistake_agent"],
            decisive_step=data["mistake_step"],
        )

    return RunLog(run_id=run_id, source_format="whowhen_release", events=events, ground_truth=ground_truth)


def load_whowhen_release_dir(directory: str | Path, is_handcrafted: bool, limit: int | None = None) -> list[RunLog]:
    """load every record from a real who&when Hand-Crafted/ or Algorithm-Generated/ dir."""
    paths = sorted(Path(directory).glob("*.json"), key=lambda p: int("".join(filter(str.isdigit, p.stem)) or 0))
    if limit is not None:
        paths = paths[:limit]
    return [load_whowhen_release_record(p, is_handcrafted) for p in paths]
