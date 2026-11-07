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


def run_system(
    run: RunLog,
    provider: LLMProvider,
    ledger: IntegrityLedger,
    *,
    use_verifier: bool = True,
    use_policy_checker: bool = True,
) -> list[AuditFinding]:
    ledger_ok, _break_index = ledger.verify()

    candidates = retrieve_candidates(run)
    claim = auditor.propose(run, provider, candidates)

    if use_verifier:
        result = verifier.verify(run, provider, claim)
        if not result.verified:
            revised = auditor.revise(run, provider, candidates, result.reason)
            revised_result = verifier.verify(run, provider, revised)
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

    return findings
