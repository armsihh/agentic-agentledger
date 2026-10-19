"""End-to-end workflow: ingest logs -> build an Integrity Ledger -> run baseline B0
-> check the implemented controls -> report accuracy and write results to disk.

Usage:
    python eval/run_baseline.py
    python eval/run_baseline.py --logs data/sample_logs
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from agentledger.baselines.b0_single_call import run_b0
from agentledger.controls import CONTROL_CATALOGUE
from agentledger.ingestion import load_logs_from_dir
from agentledger.ledger import IntegrityLedger
from agentledger.providers import get_default_provider
from agentledger.tools import check_control


def build_ledger(run) -> IntegrityLedger:
    ledger = IntegrityLedger()
    for event in run.events:
        ledger.append(
            {
                "event_id": event.event_id,
                "agent": event.agent,
                "step_index": event.step_index,
                "tool_calls": [tc.model_dump() for tc in event.tool_calls],
            }
        )
    return ledger


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--logs", default="data/sample_logs")
    args = parser.parse_args()

    provider = get_default_provider()
    print(f"Using provider: {type(provider).__name__}")

    runs = load_logs_from_dir(args.logs)
    print(f"Loaded {len(runs)} run(s) from {args.logs}")

    results = []
    correct = 0
    for run in runs:
        ledger = build_ledger(run)
        prediction = run_b0(run, provider)

        chain_ok, _ = ledger.verify()
        control_results = []
        for control in CONTROL_CATALOGUE[:2]:  # only the implemented predicates (CTRL-01/02)
            cr = check_control(control["id"], run, ledger)
            control_results.append({"control_id": cr.control_id, "passed": cr.passed, "evidence": cr.evidence})

        is_correct = (
            run.ground_truth is not None
            and prediction.agent == run.ground_truth.responsible_agent
            and prediction.step == run.ground_truth.decisive_step
        )
        correct += int(is_correct)

        results.append(
            {
                "run_id": run.run_id,
                "prediction": {"agent": prediction.agent, "step": prediction.step},
                "ground_truth": run.ground_truth.model_dump() if run.ground_truth else None,
                "correct": is_correct,
                "ledger_chain_ok": chain_ok,
                "controls": control_results,
            }
        )
        print(
            f"  {run.run_id}: predicted agent={prediction.agent} step={prediction.step} "
            f"| correct={is_correct} | ledger_ok={chain_ok}"
        )

    accuracy = correct / len(runs) if runs else 0.0
    print(f"\nB0 run-level accuracy on {len(runs)} sample run(s): {accuracy:.2%}")

    out_path = Path("results/baseline_b0_results.json")
    out_path.parent.mkdir(exist_ok=True)
    out_path.write_text(json.dumps({"accuracy": accuracy, "runs": results}, indent=2), encoding="utf-8")
    print(f"Wrote {out_path}")


if __name__ == "__main__":
    main()
