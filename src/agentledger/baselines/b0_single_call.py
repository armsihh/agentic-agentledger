"""Baseline B0 (B10): the whole log goes to one prompt, which returns a bare
verdict - no evidence citation, no ledger check, non-agentic. This is the
weakest baseline the full AgentLedger system is compared against.
"""
from __future__ import annotations

import json
from dataclasses import dataclass

from ..providers import LLMProvider
from ..schema import RunLog

_PROMPT_TEMPLATE = """You are reviewing a multi-agent run log to decide which agent and which \
step caused the task to fail. Reply with only a JSON object: {{"agent": "<name>", "step": <int>}}.

Log:
{turns}
"""


@dataclass
class B0Prediction:
    run_id: str
    agent: str
    step: int
    raw_response: str


def _format_turns(run: RunLog) -> str:
    return "\n".join(f"[{e.step_index}] {e.agent}: {e.content}" for e in run.events)


def run_b0(run: RunLog, provider: LLMProvider) -> B0Prediction:
    prompt = _PROMPT_TEMPLATE.format(turns=_format_turns(run))
    raw = provider.generate(prompt)
    try:
        parsed = json.loads(raw)
        agent, step = parsed["agent"], int(parsed["step"])
    except (json.JSONDecodeError, KeyError, ValueError):
        agent, step = "unknown", -1
    return B0Prediction(run_id=run.run_id, agent=agent, step=step, raw_response=raw)
