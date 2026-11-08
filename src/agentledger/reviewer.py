"""reviewer-facing output: turns a list of AuditFinding into a human-readable audit report
(agent, step, cited records, verified, control pass/fail), plus the ledger/provenance status
that gates whether those findings can be trusted."""
from __future__ import annotations

from typing import Any, Iterable

from .ledger import IntegrityLedger
from .provenance import ProvenanceGraph, verify_with_anchor


def render_report(
    findings: Iterable[Any],
    *,
    run_id: str | None = None,
    ledger: IntegrityLedger | None = None,
    ground_truth: dict | None = None,
    event_lookup: dict[str, str] | None = None,
) -> str:
    """findings: AuditFinding-like objects. event_lookup: optional event_id -> short text, so a
    reviewer can see what each cited record actually says."""
    findings = list(findings)
    lines: list[str] = []
    title = run_id or (findings[0].run_id if findings else "unknown run")
    lines += [f"AUDIT REPORT  run={title}", "=" * 72]

    if ledger is not None:
        ok, reason = verify_with_anchor(ledger, ledger.head_hash, len(ledger.entries))
        g = ProvenanceGraph.from_ledger(ledger)
        lines.append(
            f"Integrity: {'INTACT' if ok else 'TAMPERED (' + reason + ')'}  "
            f"entries={len(ledger.entries)}  provenance nodes={len(g.nodes)} edges={len(g.edges)}  "
            f"head={ledger.head_hash[:12]}..."
        )
        lines.append("")

    attribution = [f for f in findings if f.control_id is None]
    controls = [f for f in findings if f.control_id is not None]

    lines.append("1. Failure attribution")
    for f in attribution:
        status = "VERIFIED" if f.verified else "UNVERIFIED (treat as a hypothesis, not evidence)"
        lines.append(f"   agent={f.agent}  step={f.step}  [{status}]")
        for rid in f.cited_record_ids:
            snippet = (event_lookup or {}).get(rid)
            lines.append(f"     cites {rid}" + (f": {snippet[:90]!r}" if snippet else ""))
        if not f.cited_record_ids:
            lines.append("     cites nothing")
        if f.rationale:
            lines.append(f"     why: {f.rationale[:300]}")
        if ground_truth:
            hit = f.agent == ground_truth.get("responsible_agent") and f.step == ground_truth.get("decisive_step")
            lines.append(f"     ground truth: {ground_truth}  -> {'match' if hit else 'no match'}")
    if not attribution:
        lines.append("   (none)")

    lines += ["", "2. Control checks"]
    for f in controls:
        mark = "PASS" if f.passed else "FAIL"
        lines.append(f"   {f.control_id}  {mark}  {f.rationale[:200]}")
    if not controls:
        lines.append("   (none run)")
    failed = [f.control_id for f in controls if not f.passed]
    lines += ["", f"Summary: {len(controls) - len(failed)}/{len(controls)} controls passed"
              + (f"; failed: {', '.join(failed)}" if failed else "")]
    return "\n".join(lines)
