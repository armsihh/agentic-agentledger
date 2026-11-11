"""baseline b0: whole log, one prompt, bare verdict. non-agentic. from scratch."""
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


_MAX_LOG_CHARS = 12000  # keeps prompts under free-tier token-per-minute caps; tail-truncate like B10 describes


def _format_turns(run: RunLog) -> str:
    text = "\n".join(f"[{e.step_index}] {e.agent}: {e.content}" for e in run.events)
    if len(text) > _MAX_LOG_CHARS:
        text = "...[truncated]...\n" + text[-_MAX_LOG_CHARS:]
    return text


def run_b0(run: RunLog, provider: LLMProvider) -> B0Prediction:
    prompt = _PROMPT_TEMPLATE.format(turns=_format_turns(run))
    raw = provider.generate(prompt)
    try:
        parsed = json.loads(raw)
        agent, step = parsed["agent"], int(parsed["step"])
    except (json.JSONDecodeError, KeyError, ValueError, TypeError):
        # TypeError covers a reply that parses as valid JSON but isn't a dict (e.g. a bare
        # number or list), where parsed["agent"] raises "not subscriptable" instead of KeyError.
        agent, step = "unknown", -1
    return B0Prediction(run_id=run.run_id, agent=agent, step=step, raw_response=raw)
