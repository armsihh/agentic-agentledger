"""E3 (proposed system) / E5 (ablation): run the full Auditor->Verifier->Policy Checker
pipeline end to end and report agent-level/step-level accuracy plus verified rate, in the
same results shape as run_baseline.py / run_b1.py so the gap-resolution table can pull from
one consistent place.

usage:
    python eval/run_system.py
    python eval/run_system.py --no-verifier --no-policy-checker   (ablations)
    python eval/run_system.py --real-whowhen-root "../reference-Agents_Failure_Attribution/Who&When" --limit 20
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from agentledger.ingestion import load_logs_from_dir, load_whowhen_release_full
from agentledger.ledger import IntegrityLedger
from agentledger.orchestrator import run_system_with_trace
from agentledger.providers import get_default_provider


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
    parser.add_argument("--logs", default="data/sample_logs")
    parser.add_argument("--real-whowhen-root", default=None)
    parser.add_argument("--limit", type=int, default=None)
    parser.add_argument("--no-verifier", action="store_true")
    parser.add_argument("--no-policy-checker", action="store_true")
    parser.add_argument("--out", default="results/system_results.json")
    parser.add_argument("--trajectory-dir", default="logs", help="per-run step-by-step trace output (observability); pass '' to skip writing")
    args = parser.parse_args()

    trajectory_dir = Path(args.trajectory_dir) if args.trajectory_dir else None
    if trajectory_dir:
        trajectory_dir.mkdir(parents=True, exist_ok=True)

    provider = get_default_provider()
    print(f"Using provider: {type(provider).__name__}")

    if args.real_whowhen_root:
        runs = load_whowhen_release_full(args.real_whowhen_root, args.limit)
        print(f"Loaded {len(runs)} real Who&When run(s) from {args.real_whowhen_root}")
    else:
        runs = load_logs_from_dir(args.logs)
        print(f"Loaded {len(runs)} sample run(s) from {args.logs}")

    use_verifier = not args.no_verifier
    use_policy_checker = not args.no_policy_checker

    correct_agent = correct_both = verified_count = errors = 0
    per_run = []
    for i, run in enumerate(runs, 1):
        print(f"  {i}/{len(runs)} {run.run_id}", end="\r")
        ledger = _build_ledger(run)
        try:
            findings, trajectory = run_system_with_trace(
                run, provider, ledger, use_verifier=use_verifier, use_policy_checker=use_policy_checker
            )
        except Exception as exc:  # free-tier flakiness shouldn't lose the whole batch's progress
            errors += 1
            per_run.append({"run_id": run.run_id, "error": str(exc)})
            continue
        gap1 = findings[0]

        if trajectory_dir:
            safe_name = run.run_id.replace("/", "_")
            (trajectory_dir / f"{safe_name}.json").write_text(
                json.dumps({"run_id": run.run_id, "trajectory": trajectory}, indent=2), encoding="utf-8"
            )

        agent_ok = run.ground_truth is not None and gap1.agent == run.ground_truth.responsible_agent
        both_ok = agent_ok and run.ground_truth is not None and gap1.step == run.ground_truth.decisive_step
        correct_agent += int(agent_ok)
        correct_both += int(both_ok)
        verified_count += int(gap1.verified)

        control_findings = [
            {"control_id": f.control_id, "passed": f.passed, "rationale": f.rationale}
            for f in findings
            if f.control_id is not None
        ]
        per_run.append(
            {
                "run_id": run.run_id,
                "predicted_agent": gap1.agent,
                "predicted_step": gap1.step,
                "cited_record_ids": gap1.cited_record_ids,
                "verified": gap1.verified,
                "ground_truth": run.ground_truth.model_dump() if run.ground_truth else None,
                "agent_correct": agent_ok,
                "step_correct": both_ok,
                "control_findings": control_findings,
            }
        )

    n = len(runs) or 1
    if errors:
        print(f"\n{errors} run(s) errored out and were excluded from accuracy")
    agent_acc, step_acc, verified_rate = correct_agent / n, correct_both / n, verified_count / n
    print(
        f"\nSystem (verifier={use_verifier}, policy_checker={use_policy_checker}): "
        f"agent-level accuracy: {agent_acc:.2%} | step-level accuracy: {step_acc:.2%} | "
        f"verified rate: {verified_rate:.2%} (n={len(runs)})"
    )

    out_path = Path(args.out)
    out_path.parent.mkdir(exist_ok=True, parents=True)
    out_path.write_text(
        json.dumps(
            {
                "use_verifier": use_verifier,
                "use_policy_checker": use_policy_checker,
                "agent_accuracy": agent_acc,
                "step_accuracy": step_acc,
                "verified_rate": verified_rate,
                "provider_stats": provider.stats(),  # E6: calls, latency, char volume
                "runs": per_run,
            },
            indent=2,
        ),
        encoding="utf-8",
    )
    print(f"Wrote {out_path}")


if __name__ == "__main__":
    main()
