"""baseline b2: non-agentic rag audit -- retrieve the most relevant spans, then summarise once.
no Verifier, no ledger check gating the finding, no Policy Checker, no citation requirement, no
revision loop. from scratch; reuses the same retrieve_candidates() the real system's Retriever
uses, so B2 isolates exactly what retrieval alone buys versus B0 (whole log) and what the
Verifier/revision loop on top of it then buys versus the full system (E3).
"""
from __future__ import annotations

import json
from dataclasses import dataclass

from ..agents.retriever import retrieve_candidates
from ..providers import LLMProvider
from ..schema import Event, RunLog

_PROMPT_TEMPLATE = """You are reviewing a shortlist of candidate log records retrieved from a \
multi-agent run to decide which agent and which step caused the task to fail. Reply with only a \
JSON object, nothing else, no markdown fences: {{"agent": "<name>", "step": <int>}}.

Candidate records:
{candidates}
"""


@dataclass
class B2Prediction:
    run_id: str
    agent: str
    step: int
    raw_response: str


def _format_candidates(candidates: list[Event]) -> str:
    return "\n".join(f"[{e.event_id}] step={e.step_index} {e.agent}: {e.content}" for e in candidates)


def _extract_json_object(raw: str) -> str:
    start, end = raw.find("{"), raw.rfind("}")
    if start != -1 and end != -1 and end > start:
        return raw[start : end + 1]
    return raw


def run_b2(run: RunLog, provider: LLMProvider) -> B2Prediction:
    candidates = retrieve_candidates(run)
    prompt = _PROMPT_TEMPLATE.format(candidates=_format_candidates(candidates))
    raw = provider.generate(prompt)
    try:
        parsed = json.loads(_extract_json_object(raw))
        agent, step = parsed["agent"], int(parsed["step"])
    except Exception:
        # catches TypeError too (a reply that parses as valid JSON but isn't a dict, e.g. a
        # bare number, where parsed["agent"] raises "not subscriptable" instead of KeyError).
        agent, step = "unknown", -1
    return B2Prediction(run_id=run.run_id, agent=agent, step=step, raw_response=raw)
