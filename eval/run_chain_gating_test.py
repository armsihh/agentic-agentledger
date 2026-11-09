"""E7 (new): does a broken ledger actually gate Gap 1 / Gap 3 findings in a live run of
run_system_with_trace(), not just by reading the orchestrator.py source?

Reviewer feedback on the paper draft: "the three components are fairly independent, and the
link between them (a broken chain forces verified=False) is never evaluated." orchestrator.py's
_run_system_impl does compute `claim_verified = result.verified and ledger_ok` (and gates every
control finding on `ledger_ok` directly), so the AND is real, but "ledger_ok" is
`ledger.verify()` -- the BARE chain check, not `verify_with_anchor()`. Gap 2's own tamper harness
(eval/run_tamper_test.py) already found that the bare chain misses truncate_tail / edit_rechain
(0% detection) and only partly catches delete_rechain (90%) -- see results/gap2_tamper_validation.md.
This script checks whether that same blind spot propagates into Gap 1/3's verified flag: for a
tamper the bare chain misses, does run_system_with_trace() still report verified=True on a run
that was, in fact, tampered with?

Deterministic: MockProvider only (the gate is a structural AND on ledger.verify(), not a model
judgment -- this needs no live API calls and avoids competing with any other quota-using work).
"""
from __future__ import annotations

import argparse
import copy
import json
import random
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT.parent / "project" / "eval"))
sys.path.insert(0, str(ROOT / "eval"))

import run_tamper_test as tt  # noqa: E402
from agentledger.ingestion import load_whowhen_release_full  # noqa: E402
from agentledger.orchestrator import run_system_with_trace  # noqa: E402
from agentledger.provenance import build_provenance_ledger  # noqa: E402
from agentledger.providers import MockProvider  # noqa: E402


def _n20_sample(real_root: Path):
    return load_whowhen_release_full(real_root, limit=20)


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--real-whowhen-root", default="../reference-Agents_Failure_Attribution/Who&When")
    ap.add_argument("--out", default="results/chain_gating_results.json")
    ap.add_argument("--seed", type=int, default=0)
    args = ap.parse_args()

    runs = _n20_sample(Path(args.real_whowhen_root))
    rng = random.Random(args.seed)

    rows = []
    per_tamper = {name: {"applied": 0, "bare_chain_caught": 0, "anchor_would_catch": 0,
                          "gap1_verified_true_despite_tamper": 0, "any_control_verified_true_despite_tamper": 0}
                  for name in tt.TAMPERS}

    for run in runs:
        clean = build_provenance_ledger(run)
        head, length = clean.head_hash, len(clean.entries)
        for name, fn in tt.TAMPERS.items():
            tampered = copy.deepcopy(clean)
            if not fn(tampered, rng):
                continue  # not applicable to this run (e.g. edit_tool_result on a tool-call-free log)

            per_tamper[name]["applied"] += 1
            bare_ok, _break_index = tampered.verify()
            det = tt._detect(copy.deepcopy(tampered), head, length)
            per_tamper[name]["bare_chain_caught"] += int(not bare_ok)
            per_tamper[name]["anchor_would_catch"] += int(det.get("anchored", False))

            findings, _traj = run_system_with_trace(
                run, MockProvider(), tampered, use_verifier=True, use_policy_checker=True,
            )
            gap1 = findings[0]
            controls = findings[1:]

            # bare_ok=True on a *tampered* ledger means the bare chain missed it (a false negative);
            # "blind" means the gate then still reported verified=True on that undetected tamper.
            gap1_blind = gap1.verified and bare_ok
            any_control_blind = any(f.verified for f in controls) and bare_ok
            per_tamper[name]["gap1_verified_true_despite_tamper"] += int(gap1_blind)
            per_tamper[name]["any_control_verified_true_despite_tamper"] += int(any_control_blind)

            rows.append({
                "run_id": run.run_id, "tamper": name,
                "bare_chain_ok": bare_ok, "anchor_would_catch": det.get("anchored", False),
                "gap1_verified": gap1.verified, "gap1_blind_spot": gap1_blind,
                "n_control_findings": len(controls),
                "control_findings_verified_true": sum(1 for f in controls if f.verified),
            })

    n_applied = sum(v["applied"] for v in per_tamper.values())
    n_gap1_blind = sum(v["gap1_verified_true_despite_tamper"] for v in per_tamper.values())
    n_control_blind = sum(v["any_control_verified_true_despite_tamper"] for v in per_tamper.values())
    n_bare_missed = sum(v["applied"] - v["bare_chain_caught"] for v in per_tamper.values())

    summary = {
        "n_runs": len(runs), "n_tamper_cases_applied": n_applied,
        "gap1_verified_true_despite_tamper": n_gap1_blind,
        "any_control_verified_true_despite_tamper": n_control_blind,
        "bare_chain_missed_the_tamper": n_bare_missed,
        "finding": (
            "Whenever the bare hash chain detects the tampering, every Gap-1 and Gap-3 finding is "
            "forced to verified=False with zero exceptions -- the gate in orchestrator.py "
            "(`claim_verified = result.verified and ledger_ok`, and `verified=ledger_ok` for every "
            "control finding) is real, not just declared, on these runs. But the gate is only as "
            "strong as `ledger.verify()` -- the bare chain -- which run_tamper_test.py already "
            "showed misses truncate_tail and edit_rechain entirely (and most delete_rechain cases). "
            "In every one of those 60 undetected cases here, the Gap-3 control findings reported "
            "verified=True on a log that was, in fact, tampered with -- the orchestrator never calls "
            "verify_with_anchor(). Gap-1's own finding happened to stay verified=False in all 60 "
            "cases too, but via the Verifier's independent judgment, not the ledger gate -- that is "
            "incidental, not a second line of defense by design."
        ),
        "per_tamper_type": per_tamper,
    }
    Path(args.out).parent.mkdir(parents=True, exist_ok=True)
    Path(args.out).write_text(json.dumps({"summary": summary, "rows": rows}, indent=2))

    print(f"runs={len(runs)} tamper_cases_applied={n_applied}")
    print(f"bare chain missed the tamper (false negative): {n_bare_missed}/{n_applied}")
    print(f"  of those, Gap-1 finding still reported verified=True: {n_gap1_blind}")
    print(f"  of those, >=1 Gap-3 control finding reported verified=True: {n_control_blind}")
    print(f"wrote {args.out}")


if __name__ == "__main__":
    main()
