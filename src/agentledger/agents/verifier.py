"""verifier (gap 1): re-reads only the records an Auditor claim cites (never the whole log)
and rejects claims whose citations don't actually support them. cheap structural checks run
first (no citations, citations that don't exist) before spending a model call.
"""
from __future__ import annotations

from dataclasses import dataclass

from ..providers import LLMProvider
from ..schema import RunLog
from ..tools import read_span
from .auditor import AuditorClaim

_PROMPT_TEMPLATE = """An auditor claims that agent '{agent}' made the decisive error at step \
{step}, citing these exact log records as support:

{cited}

Rationale given: {rationale}

Do the cited records actually support this claim? Reply with only 'Yes' or 'No'.
"""


@dataclass
class VerificationResult:
    verified: bool
    reason: str


def verify(run: RunLog, provider: LLMProvider, claim: AuditorClaim) -> VerificationResult:
    if claim.agent == "unknown" or not claim.cited_record_ids:
        return VerificationResult(False, "no cited records")

    cited_events = [read_span(run, rid) for rid in claim.cited_record_ids]
    missing = [rid for rid, e in zip(claim.cited_record_ids, cited_events) if e is None]
    if missing:
        return VerificationResult(False, f"cited record ids not found in run: {missing}")

    cited_text = "\n".join(f"[{e.event_id}] step={e.step_index} {e.agent}: {e.content}" for e in cited_events)
    prompt = _PROMPT_TEMPLATE.format(agent=claim.agent, step=claim.step, cited=cited_text, rationale=claim.rationale)
    answer = provider.generate(prompt).strip().lower()
    if answer.startswith("yes"):
        return VerificationResult(True, "cited records support the claim")
    return VerificationResult(False, "verifier judged the cited records do not support the claim")
