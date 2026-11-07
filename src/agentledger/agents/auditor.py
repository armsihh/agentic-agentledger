"""auditor (gap 1): proposes which agent/step is responsible, citing specific log-record
ids from a retrieved candidate set rather than reading (or being shown) the whole log.
supports one revision pass when the Verifier rejects the citations (b8: "at most two
revisions").
"""
from __future__ import annotations

import json
from dataclasses import dataclass

from ..providers import LLMProvider
from ..schema import Event, RunLog

_PROMPT_TEMPLATE = """You are auditing a multi-agent run log to decide which agent and which \
step caused the task to fail. You may only use the candidate records below; cite the exact \
record ids that justify your answer. Reply with only a JSON object, nothing else, no markdown \
fences, and keep "rationale" to one short sentence (under 15 words) so the whole reply is brief: \
{{"agent": "<name>", "step": <int>, "cited_record_ids": ["<id>", ...], "rationale": "<short why>"}}.

Candidate records:
{candidates}
"""

_REVISION_SUFFIX = """

Your previous answer was rejected: the cited records did not support the claim \
({reason}). Revise your answer, citing records that actually support it, or say \
"unknown" if the candidates do not support any single claim.
"""


@dataclass
class AuditorClaim:
    run_id: str
    agent: str
    step: int
    cited_record_ids: list[str]
    rationale: str
    raw_response: str


def _format_candidates(candidates: list[Event]) -> str:
    return "\n".join(f"[{e.event_id}] step={e.step_index} {e.agent}: {e.content}" for e in candidates)


def _extract_json_object(raw: str) -> str:
    """models sometimes wrap the JSON in markdown fences or add stray text; pull out the
    outermost {...} span (by first/last brace) so a well-formed object still parses."""
    start, end = raw.find("{"), raw.rfind("}")
    if start != -1 and end != -1 and end > start:
        return raw[start : end + 1]
    return raw


def _parse(run_id: str, raw: str) -> AuditorClaim:
    try:
        parsed = json.loads(_extract_json_object(raw))
        agent = parsed["agent"]
        step = int(parsed["step"])
        cited = [str(c) for c in parsed.get("cited_record_ids", [])]
        rationale = str(parsed.get("rationale", ""))
    except (json.JSONDecodeError, KeyError, ValueError, TypeError):
        agent, step, cited, rationale = "unknown", -1, [], "could not parse model output"
    return AuditorClaim(run_id, agent, step, cited, rationale, raw)


def propose(run: RunLog, provider: LLMProvider, candidates: list[Event]) -> AuditorClaim:
    prompt = _PROMPT_TEMPLATE.format(candidates=_format_candidates(candidates))
    raw = provider.generate(prompt)
    return _parse(run.run_id, raw)


def revise(run: RunLog, provider: LLMProvider, candidates: list[Event], reason: str) -> AuditorClaim:
    prompt = _PROMPT_TEMPLATE.format(candidates=_format_candidates(candidates)) + _REVISION_SUFFIX.format(reason=reason)
    raw = provider.generate(prompt)
    return _parse(run.run_id, raw)
