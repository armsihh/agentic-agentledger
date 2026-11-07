"""end-to-end: ingest -> ledger -> baseline b0 -> control check -> results.

usage: python eval/run_baseline.py [--logs data/sample_logs]
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from agentledger.baselines.b0_single_call import run_b0
from agentledger.controls import CONTROL_CATALOGUE
from agentledger.ingestion import load_logs_from_dir, load_whowhen_release_full
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
    parser.add_argument("--real-whowhen-root", default=None, help="Who&When/ dir holding both Hand-Crafted/ and Algorithm-Generated/")
    parser.add_argument("--limit", type=int, default=None)
    parser.add_argument("--out", default="results/baseline_b0_results.json")
    args = parser.parse_args()

    provider = get_default_provider()
    print(f"Using provider: {type(provider).__name__}")

    if args.real_whowhen_root:
        runs = load_whowhen_release_full(args.real_whowhen_root, args.limit)
        print(f"Loaded {len(runs)} real Who&When run(s) (Hand-Crafted + Algorithm-Generated) from {args.real_whowhen_root}")
    else:
        runs = load_logs_from_dir(args.logs)
        print(f"Loaded {len(runs)} sample run(s) from {args.logs}")

    results = []
    correct_agent = correct_both = 0
    for i, run in enumerate(runs, 1):
        print(f"  {i}/{len(runs)} {run.run_id}", end="\r")
        ledger = build_ledger(run)
        prediction = run_b0(run, provider)

        chain_ok, _ = ledger.verify()
        control_results = []
        for control in CONTROL_CATALOGUE[:2]:  # only the implemented predicates
            cr = check_control(control["id"], run, ledger)
            control_results.append({"control_id": cr.control_id, "passed": cr.passed, "evidence": cr.evidence})

        agent_ok = run.ground_truth is not None and prediction.agent == run.ground_truth.responsible_agent
        both_ok = agent_ok and run.ground_truth is not None and prediction.step == run.ground_truth.decisive_step
        correct_agent += int(agent_ok)
        correct_both += int(both_ok)

        results.append(
            {
                "run_id": run.run_id,
                "prediction": {"agent": prediction.agent, "step": prediction.step},
                "ground_truth": run.ground_truth.model_dump() if run.ground_truth else None,
                "agent_correct": agent_ok,
                "step_correct": both_ok,
                "ledger_chain_ok": chain_ok,
                "controls": control_results,
            }
        )

    n = len(runs) or 1
    agent_acc, step_acc = correct_agent / n, correct_both / n
    print(f"\nB0 agent-level accuracy: {agent_acc:.2%} | step-level accuracy: {step_acc:.2%} (n={len(runs)})")

    out_path = Path(args.out)
    out_path.parent.mkdir(exist_ok=True, parents=True)
    out_path.write_text(
        json.dumps({"agent_accuracy": agent_acc, "step_accuracy": step_acc, "runs": results}, indent=2),
        encoding="utf-8",
    )
    print(f"Wrote {out_path}")


if __name__ == "__main__":
    main()
