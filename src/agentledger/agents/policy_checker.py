"""policy checker (gap 3): runs every implemented control predicate over a ledgered
trajectory and attaches evidence to each pass/fail. unimplemented predicates (declared in
the catalogue but not yet built) are skipped, not silently counted as passing.
"""
from __future__ import annotations

from dataclasses import dataclass

from ..controls import CONTROL_CATALOGUE, ControlResult
from ..ledger import IntegrityLedger
from ..schema import RunLog


@dataclass
class PolicyCheckResult:
    control_id: str
    passed: bool
    evidence: str
    implemented: bool


def run_policy_checks(run: RunLog, ledger: IntegrityLedger) -> list[PolicyCheckResult]:
    results: list[PolicyCheckResult] = []
    for control in CONTROL_CATALOGUE:
        try:
            r: ControlResult = control["predicate"](run, ledger)
            results.append(PolicyCheckResult(r.control_id, r.passed, r.evidence, implemented=True))
        except NotImplementedError:
            results.append(PolicyCheckResult(control["id"], False, "predicate not yet implemented", implemented=False))
    return results
