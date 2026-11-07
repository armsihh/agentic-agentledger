"""E4 (Gap 3): run the Policy Checker over the injected-violation suite and score its
pass/fail against the planted ground truth (precision/recall/F1 per control).

usage: python eval/run_policy_eval.py [--violations-dir data/injected_violations]
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from agentledger.agents.policy_checker import run_policy_checks
from agentledger.ingestion import load_whowhen_log
from agentledger.ledger import IntegrityLedger

_SCORED_CONTROLS = ["CTRL-03", "CTRL-06", "CTRL-07", "CTRL-11"]


def _build_ledger(run) -> IntegrityLedger:
    ledger = IntegrityLedger()
    for event in run.events:
        ledger.append(
            {
                "event_id": event.event_id,
                "agent": event.agent,
                "tool_calls": [tc.model_dump() for tc in event.tool_calls],
            }
        )
    return ledger


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--violations-dir", default="data/injected_violations")
    parser.add_argument("--out", default="results/gap3_policy_eval.json")
    args = parser.parse_args()

    paths = sorted(Path(args.violations_dir).glob("*.json"))
    if not paths:
        raise SystemExit(f"no injected-violation files in {args.violations_dir}; run make_injected_violations.py first")

    counts = {c: {"tp": 0, "fp": 0, "fn": 0, "tn": 0} for c in _SCORED_CONTROLS}
    per_run = []

    for path in paths:
        raw = json.loads(path.read_text(encoding="utf-8"))
        violated = set(raw.get("violated_controls", []))
        run = load_whowhen_log(path)
        ledger = _build_ledger(run)
        results = {r.control_id: r.passed for r in run_policy_checks(run, ledger) if r.implemented}

        for control in _SCORED_CONTROLS:
            predicted_violation = not results.get(control, True)  # pass=False means "violation detected"
            actual_violation = control in violated
            if predicted_violation and actual_violation:
                counts[control]["tp"] += 1
            elif predicted_violation and not actual_violation:
                counts[control]["fp"] += 1
            elif not predicted_violation and actual_violation:
                counts[control]["fn"] += 1
            else:
                counts[control]["tn"] += 1

        per_run.append({"run_id": run.run_id, "planted_violations": sorted(violated), "control_results": results})

    metrics = {}
    for control, c in counts.items():
        precision = c["tp"] / (c["tp"] + c["fp"]) if (c["tp"] + c["fp"]) else 0.0
        recall = c["tp"] / (c["tp"] + c["fn"]) if (c["tp"] + c["fn"]) else 0.0
        f1 = 2 * precision * recall / (precision + recall) if (precision + recall) else 0.0
        metrics[control] = {"precision": precision, "recall": recall, "f1": f1, **c}
        print(f"{control}: precision={precision:.2f} recall={recall:.2f} f1={f1:.2f} ({c})")

    out_path = Path(args.out)
    out_path.parent.mkdir(exist_ok=True, parents=True)
    out_path.write_text(json.dumps({"metrics": metrics, "runs": per_run}, indent=2), encoding="utf-8")
    print(f"\nWrote {out_path}")


if __name__ == "__main__":
    main()
