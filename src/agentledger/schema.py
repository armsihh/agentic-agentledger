"""Normalised event schema that every log format is ingested into (B8 state/context structure)."""
from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field

Role = Literal["agent", "tool", "system", "user"]


class ToolCall(BaseModel):
    name: str
    arguments: dict[str, Any] = Field(default_factory=dict)
    result: str | None = None


class Event(BaseModel):
    """One normalised step in an agent run, regardless of the source log format."""

    event_id: str
    run_id: str
    step_index: int
    agent: str
    role: Role
    content: str
    tool_calls: list[ToolCall] = Field(default_factory=list)
    timestamp: str | None = None


class GroundTruth(BaseModel):
    """Annotated failure attribution, when the source log carries one (e.g. Who&When)."""

    responsible_agent: str
    decisive_step: int


class RunLog(BaseModel):
    """A full normalised run: an ordered sequence of events plus optional ground truth."""

    run_id: str
    source_format: str
    events: list[Event]
    ground_truth: GroundTruth | None = None

    def event_by_id(self, event_id: str) -> Event | None:
        return next((e for e in self.events if e.event_id == event_id), None)
