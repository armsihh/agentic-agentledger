"""Control catalogue (Gap 3): predicates compiled from ISO/IEC 42001 management-system
clauses and NIST AI RMF functions, evaluated over a ledgered run.

Phase 1 ships the catalogue structure and two fully implemented predicates
(CTRL-01, CTRL-02); the rest are declared with a clear NotImplementedError so the
catalogue's shape is final even though most predicates are filled in during
Phase 2's Policy Checker work.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Callable

from .ledger import IntegrityLedger
from .schema import RunLog


@dataclass
class ControlResult:
    control_id: str
    passed: bool
    evidence: str


def _ctrl_01_record_keeping(run: RunLog, ledger: IntegrityLedger) -> ControlResult:
    """ISO/IEC 42001 Clause 8 (operational control) / NIST AI RMF Govern:
    every event in the run must have a matching, verified ledger entry."""
    ok, break_index = ledger.verify()
    complete = len(ledger.entries) == len(run.events)
    passed = ok and complete
    evidence = (
        f"ledger_entries={len(ledger.entries)} events={len(run.events)} chain_ok={ok} "
        f"break_index={break_index}"
    )
    return ControlResult("CTRL-01", passed, evidence)


def _ctrl_02_tool_call_logged(run: RunLog, ledger: IntegrityLedger) -> ControlResult:
    """ISO/IEC 42001 Clause 9 (monitoring) / NIST AI RMF Measure:
    every tool call made by an agent must appear in some ledgered payload."""
    tool_call_names = {tc.name for e in run.events for tc in e.tool_calls}
    ledgered_names = set()
    for entry in ledger.entries:
        for tc in entry.payload.get("tool_calls", []):
            ledgered_names.add(tc.get("name"))
    missing = tool_call_names - ledgered_names
    passed = not missing
    evidence = f"tool_calls={sorted(tool_call_names)} missing_from_ledger={sorted(missing)}"
    return ControlResult("CTRL-02", passed, evidence)


def _not_implemented(control_id: str) -> Callable[[RunLog, IntegrityLedger], ControlResult]:
    def _predicate(run: RunLog, ledger: IntegrityLedger) -> ControlResult:
        raise NotImplementedError(f"{control_id} predicate is planned for Phase 2 (Policy Checker)")

    return _predicate


CONTROL_CATALOGUE: list[dict] = [
    {
        "id": "CTRL-01",
        "name": "Complete, verified record-keeping",
        "source": "ISO/IEC 42001:2023",
        "clause_or_function": "Clause 8 - Operational control",
        "predicate": _ctrl_01_record_keeping,
    },
    {
        "id": "CTRL-02",
        "name": "Tool calls are logged",
        "source": "ISO/IEC 42001:2023",
        "clause_or_function": "Clause 9 - Monitoring, measurement, analysis and evaluation",
        "predicate": _ctrl_02_tool_call_logged,
    },
    {
        "id": "CTRL-03",
        "name": "Human oversight before high-risk actions",
        "source": "NIST AI RMF",
        "clause_or_function": "Govern",
        "predicate": _not_implemented("CTRL-03"),
    },
    {
        "id": "CTRL-04",
        "name": "Risk treatment plan covers the run's failure modes",
        "source": "ISO/IEC 42001:2023",
        "clause_or_function": "Clause 6 - Planning / risk treatment",
        "predicate": _not_implemented("CTRL-04"),
    },
    {
        "id": "CTRL-05",
        "name": "Findings are traceable to AI RMF Map function outputs",
        "source": "NIST AI RMF",
        "clause_or_function": "Map",
        "predicate": _not_implemented("CTRL-05"),
    },
    {
        "id": "CTRL-06",
        "name": "Performance/impact metrics are measured per run",
        "source": "NIST AI RMF",
        "clause_or_function": "Measure",
        "predicate": _not_implemented("CTRL-06"),
    },
    {
        "id": "CTRL-07",
        "name": "Corrective action taken on confirmed violations",
        "source": "NIST AI RMF",
        "clause_or_function": "Manage",
        "predicate": _not_implemented("CTRL-07"),
    },
    {
        "id": "CTRL-08",
        "name": "Internal audit of the ledger is performed",
        "source": "ISO/IEC 42001:2023",
        "clause_or_function": "Clause 9 - Internal audit",
        "predicate": _not_implemented("CTRL-08"),
    },
    {
        "id": "CTRL-09",
        "name": "Nonconformities are recorded and tracked",
        "source": "ISO/IEC 42001:2023",
        "clause_or_function": "Clause 10 - Improvement",
        "predicate": _not_implemented("CTRL-09"),
    },
    {
        "id": "CTRL-10",
        "name": "Authorisation boundaries for autonomous actions are respected",
        "source": "NIST AI RMF",
        "clause_or_function": "Govern",
        "predicate": _not_implemented("CTRL-10"),
    },
    {
        "id": "CTRL-11",
        "name": "Data handling in tool calls matches declared scope",
        "source": "ISO/IEC 42001:2023",
        "clause_or_function": "Clause 8 - Operational control",
        "predicate": _not_implemented("CTRL-11"),
    },
    {
        "id": "CTRL-12",
        "name": "Context/resource constraints documented and enforced",
        "source": "NIST AI RMF",
        "clause_or_function": "Map",
        "predicate": _not_implemented("CTRL-12"),
    },
]


def check_control(control_id: str, run: RunLog, ledger: IntegrityLedger) -> ControlResult:
    entry = next(c for c in CONTROL_CATALOGUE if c["id"] == control_id)
    return entry["predicate"](run, ledger)
