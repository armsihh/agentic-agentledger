"""orchestrator (b8): Auditor (+Retriever) -> Verifier -> Policy Checker, gated by the
Integrity Ledger. This is the single entry point Areej's evaluation harness calls; the
use_verifier / use_policy_checker flags are the E5 ablation switches.
"""
from __future__ import annotations

from dataclasses import dataclass, field

from .agents import auditor, verifier
from .agents.policy_checker import run_policy_checks
from .agents.retriever import retrieve_candidates
from .ledger import IntegrityLedger
from .providers import LLMProvider
from .schema import RunLog


@dataclass
class AuditFinding:
    run_id: str
    agent: str
    step: int
    control_id: str | None  # None for the plain Gap-1 attribution finding
    passed: bool | None  # None when not a control check
    cited_record_ids: list[str] = field(default_factory=list)
    verified: bool = False  # did the Verifier accept this claim's citations (and is the ledger intact)
    rationale: str = ""


def _run_system_impl(
    run: RunLog,
    provider: LLMProvider,
    ledger: IntegrityLedger,
    use_verifier: bool,
    use_policy_checker: bool,
    causal_verifier: bool | str = False,
) -> tuple[list[AuditFinding], list[dict]]:
    """shared implementation. returns (findings, trajectory) -- trajectory is the step-by-step
    observability log (retrieval -> propose -> verify -> [revise -> re-verify] -> policy checks)
    required by the Phase 2 brief's "logged agent trajectories" requirement; `run_system()` below
    keeps its existing return type (just findings) since that's the stable interface Areej's
    harness is built against, and `run_system_with_trace()` is the new entry point for anyone
    who wants the full trace (see `eval/run_system.py`'s --log-trajectories flag)."""
    trajectory: list[dict] = []

    ledger_ok, break_index = ledger.verify()
    trajectory.append({"stage": "ledger_check", "ledger_ok": ledger_ok, "break_index": break_index})

    candidates = retrieve_candidates(run)
    trajectory.append({"stage": "retrieve", "candidate_ids": [e.event_id for e in candidates]})

    claim = auditor.propose(run, provider, candidates)
    trajectory.append(
        {"stage": "auditor_propose", "raw_response": claim.raw_response, "agent": claim.agent,
         "step": claim.step, "cited_record_ids": claim.cited_record_ids, "rationale": claim.rationale}
    )

    if use_verifier:
        result = verifier.verify(run, provider, claim, causal=causal_verifier)
        trajectory.append(
            {"stage": "verifier_check", "raw_response": result.raw_response, "verified": result.verified,
             "reason": result.reason}
        )
        if not result.verified:
            revised = auditor.revise(run, provider, candidates, result.reason)
            trajectory.append(
                {"stage": "auditor_revise", "raw_response": revised.raw_response, "agent": revised.agent,
                 "step": revised.step, "cited_record_ids": revised.cited_record_ids, "rationale": revised.rationale}
            )
            revised_result = verifier.verify(run, provider, revised, causal=causal_verifier)
            trajectory.append(
                {"stage": "verifier_recheck", "raw_response": revised_result.raw_response,
                 "verified": revised_result.verified, "reason": revised_result.reason}
            )
            claim, result = revised, revised_result
        claim_verified = result.verified and ledger_ok
    else:
        claim_verified = ledger_ok  # ablation: trust the claim's citations without re-reading them

    findings = [
        AuditFinding(
            run_id=run.run_id,
            agent=claim.agent,
            step=claim.step,
            control_id=None,
            passed=None,
            cited_record_ids=claim.cited_record_ids,
            verified=claim_verified,
            rationale=claim.rationale,
        )
    ]

    if use_policy_checker:
        for pr in run_policy_checks(run, ledger):
            if not pr.implemented:
                continue
            trajectory.append(
                {"stage": "policy_check", "control_id": pr.control_id, "passed": pr.passed, "evidence": pr.evidence}
            )
            findings.append(
                AuditFinding(
                    run_id=run.run_id,
                    agent="n/a",
                    step=-1,
                    control_id=pr.control_id,
                    passed=pr.passed,
                    cited_record_ids=[],
                    verified=ledger_ok,
                    rationale=pr.evidence,
                )
            )

    return findings, trajectory


def run_system(
    run: RunLog,
    provider: LLMProvider,
    ledger: IntegrityLedger,
    *,
    use_verifier: bool = True,
    use_policy_checker: bool = True,
    causal_verifier: bool | str = False,
) -> list[AuditFinding]:
    findings, _trajectory = _run_system_impl(run, provider, ledger, use_verifier, use_policy_checker, causal_verifier)
    return findings


def run_system_with_trace(
    run: RunLog,
    provider: LLMProvider,
    ledger: IntegrityLedger,
    *,
    use_verifier: bool = True,
    use_policy_checker: bool = True,
    causal_verifier: bool | str = False,
) -> tuple[list[AuditFinding], list[dict]]:
    """same as run_system(), plus the full step-by-step trajectory log (see
    `_run_system_impl`'s docstring). Used by `eval/run_system.py` to populate `logs/`."""
    return _run_system_impl(run, provider, ledger, use_verifier, use_policy_checker, causal_verifier)
