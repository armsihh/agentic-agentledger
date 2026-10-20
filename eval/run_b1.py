"""run baseline b1 (three attribution methods) end-to-end, report accuracy.

default: synthetic sample logs. pass --real-whowhen-dir to use the real
benchmark from the cloned reference repo instead.

usage:
    python eval/run_b1.py
    python eval/run_b1.py --method step_by_step
    python eval/run_b1.py --real-whowhen-dir "../reference-Agents_Failure_Attribution/Who&When/Hand-Crafted" --is-handcrafted --limit 20
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from agentledger.baselines.b1_whowhen_reference import METHODS, run_b1
from agentledger.ingestion import load_logs_from_dir, load_whowhen_release_dir
from agentledger.providers import get_default_provider


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--logs", default="data/sample_logs")
    parser.add_argument("--real-whowhen-dir", default=None)
    parser.add_argument("--is-handcrafted", action="store_true")
    parser.add_argument("--limit", type=int, default=None)
    parser.add_argument("--method", choices=list(METHODS) + ["all"], default="all")
    args = parser.parse_args()

    provider = get_default_provider()
    print(f"Using provider: {type(provider).__name__}")

    if args.real_whowhen_dir:
        runs = load_whowhen_release_dir(args.real_whowhen_dir, args.is_handcrafted, args.limit)
        print(f"Loaded {len(runs)} real Who&When run(s) from {args.real_whowhen_dir}")
    else:
        runs = load_logs_from_dir(args.logs)
        print(f"Loaded {len(runs)} sample run(s) from {args.logs}")

    methods = list(METHODS) if args.method == "all" else [args.method]
    summary: dict[str, dict] = {}

    for method in methods:
        correct_agent = correct_both = 0
        per_run = []
        for run in runs:
            pred = run_b1(run, provider, method)
            agent_ok = run.ground_truth is not None and pred.agent == run.ground_truth.responsible_agent
            both_ok = agent_ok and run.ground_truth is not None and pred.step == run.ground_truth.decisive_step
            correct_agent += int(agent_ok)
            correct_both += int(both_ok)
            per_run.append(
                {
                    "run_id": run.run_id,
                    "predicted_agent": pred.agent,
                    "predicted_step": pred.step,
                    "ground_truth": run.ground_truth.model_dump() if run.ground_truth else None,
                    "agent_correct": agent_ok,
                    "step_correct": both_ok,
                }
            )
        n = len(runs) or 1
        agent_acc, step_acc = correct_agent / n, correct_both / n
        print(f"\n[{method}] agent-level accuracy: {agent_acc:.2%} | step-level accuracy: {step_acc:.2%}")
        summary[method] = {"agent_accuracy": agent_acc, "step_accuracy": step_acc, "runs": per_run}

    out_path = Path("results/baseline_b1_results.json")
    out_path.parent.mkdir(exist_ok=True)
    out_path.write_text(json.dumps(summary, indent=2), encoding="utf-8")
    print(f"\nWrote {out_path}")


if __name__ == "__main__":
    main()
