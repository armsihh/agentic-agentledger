"""baseline b1: base paper's three attribution methods, re-implemented on our schema.

adapted from ag2ai/Agents_Failure_Attribution, Automated_FA/Lib/utils.py (mit).
reference clone kept outside this repo at ../reference-Agents_Failure_Attribution.
prompts/control flow mirror that file; schema and provider are ours.

model note: the reference code needs azure openai or a local gpu for llama/qwen,
neither available here. runs through our own provider (mock or anthropic) instead.
"""
from __future__ import annotations

import random
from dataclasses import dataclass

from ..providers import LLMProvider
from ..schema import RunLog


@dataclass
class B1Prediction:
    run_id: str
    method: str
    agent: str
    step: int
    raw_response: str


_MAX_LOG_CHARS = 12000  # keeps prompts under free-tier token-per-minute caps; tail-truncate like B0


def _history_text(run: RunLog, start: int = 0, end: int | None = None) -> str:
    end = len(run.events) - 1 if end is None else end
    text = "\n".join(f"[{i}] {run.events[i].agent}: {run.events[i].content}" for i in range(start, end + 1))
    if len(text) > _MAX_LOG_CHARS:
        text = "...[truncated]...\n" + text[-_MAX_LOG_CHARS:]
    return text


# all-at-once: mirrors Lib/utils.py::all_at_once

def _all_at_once_prompt(run: RunLog) -> str:
    return (
        "You are an AI assistant tasked with analyzing a multi-agent conversation history when "
        "solving a real world problem. Identify which agent made an error, at which step, and "
        "explain the reason for the error.\n\nHere's the conversation:\n\n"
        + _history_text(run)
        + "\n\nBased on this conversation, please predict the following:\n"
        "1. The name of the agent who made a mistake that is directly responsible for the wrong "
        "solution. If no agent makes an obvious mistake, decide one single agent.\n"
        "2. In which step the mistake agent first made the mistake (0-indexed).\n"
        "3. The reason for your prediction.\n"
        'Reply with only a JSON object: {"agent": "<name>", "step": <int>}.'
    )


def run_all_at_once(run: RunLog, provider: LLMProvider) -> B1Prediction:
    import json

    raw = provider.generate(_all_at_once_prompt(run))
    try:
        parsed = json.loads(raw)
        agent, step = parsed["agent"], int(parsed["step"])
    except Exception:
        # catches TypeError too (a reply that parses as valid JSON but isn't a dict, e.g. a
        # bare number, where parsed["agent"] raises "not subscriptable" instead of KeyError).
        agent, step = "unknown", -1
    return B1Prediction(run.run_id, "all_at_once", agent, step, raw)


# step-by-step: mirrors Lib/utils.py::step_by_step

def _step_prompt(run: RunLog, idx: int) -> str:
    agent = run.events[idx].agent
    return (
        "You are an AI assistant evaluating the correctness of each step in an ongoing multi-agent "
        f"conversation.\nConversation so far:\n{_history_text(run, 0, idx)}\n"
        f"The most recent step ({idx}) was by '{agent}'.\n"
        "Does this most recent step contain an error that could derail the task? "
        "Reply with only 'Yes' or 'No'."
    )


def run_step_by_step(run: RunLog, provider: LLMProvider) -> B1Prediction:
    for idx, event in enumerate(run.events):
        answer = provider.generate(_step_prompt(run, idx)).strip().lower()
        if answer.startswith("yes"):
            return B1Prediction(run.run_id, "step_by_step", event.agent, idx, answer)
    last = run.events[-1] if run.events else None
    return B1Prediction(run.run_id, "step_by_step", last.agent if last else "unknown", len(run.events) - 1, "no")


# binary search: mirrors Lib/utils.py::binary_search / _find_error_in_segment_recursive

def _segment_prompt(run: RunLog, start: int, end: int) -> str:
    mid = start + (end - start) // 2
    return (
        "Multiple agents are collaborating on a task. Identify which half of this conversation "
        f"segment (steps {start}-{end}) contains the step with the most critical error.\n\n"
        f"{_history_text(run, start, end)}\n\n"
        f"Reply with only 'upper half' (steps {start}-{mid}) or 'lower half' (steps {mid + 1}-{end})."
    )


def run_binary_search(run: RunLog, provider: LLMProvider) -> B1Prediction:
    start, end = 0, len(run.events) - 1
    if end < 0:
        return B1Prediction(run.run_id, "binary_search", "unknown", -1, "")
    raw = ""
    while start < end:
        mid = start + (end - start) // 2
        raw = provider.generate(_segment_prompt(run, start, end)).lower()
        if "upper half" in raw:
            end = mid
        elif "lower half" in raw:
            start = mid + 1
        else:
            # same random fallback as the reference implementation
            if random.random() < 0.5:
                end = mid
            else:
                start = mid + 1
    return B1Prediction(run.run_id, "binary_search", run.events[start].agent, start, raw)


METHODS = {
    "all_at_once": run_all_at_once,
    "step_by_step": run_step_by_step,
    "binary_search": run_binary_search,
}


def run_b1(run: RunLog, provider: LLMProvider, method: str) -> B1Prediction:
    if method not in METHODS:
        raise ValueError(f"unknown b1 method '{method}', choose from {list(METHODS)}")
    return METHODS[method](run, provider)
