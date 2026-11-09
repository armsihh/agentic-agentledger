"""E? baseline B2: non-agentic RAG audit (retrieve once, summarise once, no Verifier/ledger-gate/
Policy Checker). Required comparison point per the Phase 1 plan (B10); previously missing.

usage: python eval/run_b2.py --real-whowhen-root "../reference-Agents_Failure_Attribution/Who&When" --limit 20
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from agentledger.baselines.b2_rag_audit import run_b2
from agentledger.ingestion import load_logs_from_dir, load_whowhen_release_full
from agentledger.providers import get_default_provider


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--logs", default="data/sample_logs")
    parser.add_argument("--real-whowhen-root", default=None)
    parser.add_argument("--limit", type=int, default=None)
    parser.add_argument("--out", default="results/baseline_b2_results.json")
    args = parser.parse_args()

    provider = get_default_provider()
    print(f"Using provider: {type(provider).__name__}")

    if args.real_whowhen_root:
        runs = load_whowhen_release_full(args.real_whowhen_root, args.limit)
        print(f"Loaded {len(runs)} real Who&When run(s) from {args.real_whowhen_root}")
    else:
        runs = load_logs_from_dir(args.logs)
        print(f"Loaded {len(runs)} sample run(s) from {args.logs}")

    results = []
    correct_agent = correct_both = errors = 0
    for i, run in enumerate(runs, 1):
        print(f"  {i}/{len(runs)} {run.run_id}", end="\r")
        try:
            prediction = run_b2(run, provider)
        except Exception as exc:  # free-tier flakiness shouldn't lose the whole batch's progress
            errors += 1
            results.append({"run_id": run.run_id, "error": str(exc)})
            continue

        agent_ok = run.ground_truth is not None and prediction.agent == run.ground_truth.responsible_agent
        both_ok = agent_ok and run.ground_truth is not None and prediction.step == run.ground_truth.decisive_step
        correct_agent += int(agent_ok)
        correct_both += int(both_ok)

        results.append(
            {
                "run_id": run.run_id,
                "predicted_agent": prediction.agent,
                "predicted_step": prediction.step,
                "ground_truth": run.ground_truth.model_dump() if run.ground_truth else None,
                "agent_correct": agent_ok,
                "step_correct": both_ok,
            }
        )

    n = len(runs) or 1
    if errors:
        print(f"\n{errors} run(s) errored out and were excluded from accuracy")
    agent_acc, step_acc = correct_agent / n, correct_both / n
    print(f"\nB2 (non-agentic RAG audit) agent-level accuracy: {agent_acc:.2%} | step-level accuracy: {step_acc:.2%} (n={len(runs)})")

    out_path = Path(args.out)
    out_path.parent.mkdir(exist_ok=True, parents=True)
    out_path.write_text(
        json.dumps(
            {"agent_accuracy": agent_acc, "step_accuracy": step_acc, "provider_stats": provider.stats(), "runs": results},
            indent=2,
        ),
        encoding="utf-8",
    )
    print(f"Wrote {out_path}")


if __name__ == "__main__":
    main()
