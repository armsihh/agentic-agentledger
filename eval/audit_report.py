"""print a reviewer-readable audit report for one run.

usage:
    python eval/audit_report.py --from-results results/system_results.json --index 0
    python eval/audit_report.py --logs data/sample_logs --index 0     (live, offline MockProvider)
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))

import json

from agentledger.ingestion import load_logs_from_dir
from agentledger.orchestrator import AuditFinding, run_system
from agentledger.providers import MockProvider
from agentledger.provenance import build_provenance_ledger
from agentledger.reviewer import render_report


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--from-results", help="a results/system_results*.json file (no LLM calls needed)")
    ap.add_argument("--logs", default="data/sample_logs")
    ap.add_argument("--index", type=int, default=0)
    ap.add_argument("--out", help="also write the report to this file")
    args = ap.parse_args()

    if args.from_results:
        data = json.loads(Path(args.from_results).read_text(encoding="utf-8"))
        r = data["runs"][args.index]
        if "error" in r:
            sys.exit(f"run {r['run_id']} errored during the original experiment: {r['error']}")
        findings = [AuditFinding(r["run_id"], r["predicted_agent"], r["predicted_step"], None, None,
                                 r["cited_record_ids"], r["verified"], "")]
        findings += [AuditFinding(r["run_id"], "n/a", -1, c["control_id"], c["passed"], [], True, c["rationale"])
                     for c in r["control_findings"]]
        text = render_report(findings, run_id=r["run_id"], ground_truth=r.get("ground_truth"))
    else:
        run = load_logs_from_dir(args.logs)[args.index]
        ledger = build_provenance_ledger(run)
        findings = run_system(run, MockProvider(), ledger)
        lookup = {e.event_id: e.content for e in run.events}
        gt = run.ground_truth.model_dump() if run.ground_truth else None
        text = render_report(findings, run_id=run.run_id, ledger=ledger, ground_truth=gt, event_lookup=lookup)
    print(text)
    if args.out:
        Path(args.out).write_text(text, encoding="utf-8")


if __name__ == "__main__":
    main()
