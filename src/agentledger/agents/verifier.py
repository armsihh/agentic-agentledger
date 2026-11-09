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

Judge only whether the cited records are relevant and consistent with this claim -- not whether
they are the only possible explanation, and not requiring every cited record to independently
prove it on its own. If at least one cited record clearly shows this agent's action or statement
at (or near) this step, and nothing in the cited records contradicts the claim, answer 'Yes'.
Otherwise answer 'No'. Reply with only 'Yes' or 'No'.
"""
# Recalibrated 2026-11-07: the original wording ("do the cited records actually support this
# claim?") measured as high-precision/low-recall on the n=20 real sample -- all 4 fully-correct
# predictions in that sample were still rejected (see results/failure_analysis_gap1.md's
# "Verifier-calibration note"). This loosens the bar from "proves" to "relevant and consistent,"
# per that file's own stated fix. Validated live 2026-11-09 on a clean n=20/20 rerun: verified
# rate rose from 5% to 60% as intended, but the real remaining problem turned out to be causal,
# not textual -- see _CAUSAL_PROMPT_TEMPLATE below.

_CAUSAL_PROMPT_TEMPLATE = """An auditor claims that agent '{agent}' made the decisive error at step \
{step}, citing these exact log records as support:

{cited}

Rationale given: {rationale}

Judge whether the cited records show that THIS agent is actually responsible for causing the
failure -- not merely that an error, failure, or exception is mentioned at or near this agent's
turn. A tool-execution step (for example a terminal reporting a traceback or exit code) is NOT
evidence that the tool itself is responsible if the error it reports was actually caused by, or is
merely downstream of, a different agent's earlier mistake. If the cited records show this agent's
own action or statement actually caused the problem (or, for a correct completion, actually
satisfied the task), answer 'Yes'. If the cited records only show an error occurring nearby
without showing this specific agent caused it, answer 'No'. Reply with only 'Yes' or 'No'.
"""
# Added 2026-11-09 as a direct test of whether asking the Verifier to judge causation (not just
# textual support) catches the Computer_terminal attribution bias documented in
# results/failure_analysis_gap1.md (5 of 6 verified-but-wrong claims in the n=20 real run blamed
# the tool-execution step for an error it only reported). Opt-in via verify(..., causal=True) so
# the default pipeline behavior (and every existing test) is unchanged; see
# eval/run_system.py --causal-verifier for the ablation runner.


@dataclass
class VerificationResult:
    verified: bool
    reason: str
    raw_response: str = ""  # "" when rejected by a structural check before any LLM call was made


def verify(run: RunLog, provider: LLMProvider, claim: AuditorClaim, *, causal: bool = False) -> VerificationResult:
    if claim.agent == "unknown" or not claim.cited_record_ids:
        return VerificationResult(False, "no cited records")

    cited_events = [read_span(run, rid) for rid in claim.cited_record_ids]
    missing = [rid for rid, e in zip(claim.cited_record_ids, cited_events) if e is None]
    if missing:
        return VerificationResult(False, f"cited record ids not found in run: {missing}")

    cited_text = "\n".join(f"[{e.event_id}] step={e.step_index} {e.agent}: {e.content}" for e in cited_events)
    template = _CAUSAL_PROMPT_TEMPLATE if causal else _PROMPT_TEMPLATE
    prompt = template.format(agent=claim.agent, step=claim.step, cited=cited_text, rationale=claim.rationale)
    raw = provider.generate(prompt)
    answer = raw.strip().lower()
    if answer.startswith("yes"):
        return VerificationResult(True, "cited records support the claim", raw)
    return VerificationResult(False, "verifier judged the cited records do not support the claim", raw)
