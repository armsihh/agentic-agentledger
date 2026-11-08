"""E4 (Gap 2): tamper-injection harness for the Integrity Ledger + provenance graph.

for every clean run, builds a provenance ledger (src/agentledger/provenance.py), then applies a
batch of injected edits / deletions / re-orderings / insertions / truncations and checks whether
verification flags each one. also verifies every *clean* ledger to measure false alarms, and
measures per-event overhead. No LLM calls -- fully deterministic given --seed.

three verification modes are reported separately because they have different threat models:
    chain          IntegrityLedger.verify() only (bare hash chain)
    chain+graph    chain + provenance-graph structural consistency
    anchored       chain + graph + external anchor (head hash + length saved at write time)
the attacks "truncate_tail" and "*_rechain" (attacker recomputes every hash) are *by construction*
invisible to an unanchored chain; the anchored column is what catches them.

usage:
    python eval/run_tamper_test.py
    python eval/run_tamper_test.py --reps 3 --seed 7 --out results/tamper_results.json
"""
from __future__ import annotations

import argparse
import copy
import json
import random
import statistics
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))

from agentledger.ingestion import load_logs_from_dir, load_whowhen_release_full
from agentledger.ledger import GENESIS_HASH, IntegrityLedger, LedgerEntry, _hash_entry
from agentledger.provenance import build_provenance_ledger, verify_with_anchor


def _rechain(ledger: IntegrityLedger, start: int = 0) -> None:
    """what a capable attacker does: recompute every hash from `start` so the chain is internally valid."""
    prev = ledger.entries[start - 1].hash if start > 0 else GENESIS_HASH
    for i in range(start, len(ledger.entries)):
        e = ledger.entries[i]
        e.index = i
        e.prev_hash = prev
        e.hash = _hash_entry(prev, e.payload)
        prev = e.hash


def _renumber(ledger: IntegrityLedger) -> None:
    for i, e in enumerate(ledger.entries):
        e.index = i


# --- tamper operations: each mutates the ledger in place; return False if not applicable -------------

def edit_content(l, r):
    e = r.choice(l.entries)
    e.payload["content"] = e.payload["content"] + " [edited]"
    return True


def edit_agent(l, r):
    e = r.choice(l.entries)
    e.payload["agent"] = e.payload["agent"] + "_forged"
    return True


def edit_tool_result(l, r):
    cands = [e for e in l.entries if e.payload["tool_calls"]]
    if not cands:
        return False
    r.choice(cands).payload["tool_calls"][0]["result"] = "forged result"
    return True


def edit_provenance_link(l, r):
    e = r.choice(l.entries)
    e.payload["prov"]["attributed_to"] = "agent:someone_else"
    return True


def edit_last_entry(l, r):
    l.entries[-1].payload["content"] += " [edited]"
    return True


def delete_middle(l, r):
    if len(l.entries) < 3:
        return False
    del l.entries[r.randrange(1, len(l.entries) - 1)]
    _renumber(l)
    return True


def delete_first(l, r):
    if len(l.entries) < 2:
        return False
    del l.entries[0]
    _renumber(l)
    return True


def reorder_swap(l, r):
    if len(l.entries) < 2:
        return False
    i = r.randrange(len(l.entries) - 1)
    l.entries[i], l.entries[i + 1] = l.entries[i + 1], l.entries[i]
    _renumber(l)
    return True


def insert_forged(l, r):
    pos = r.randrange(len(l.entries) + 1)
    forged = copy.deepcopy(l.entries[0].payload)
    forged["event_id"] = "forged-event"
    forged["content"] = "forged message"
    l.entries.insert(pos, LedgerEntry(pos, "x", "x", forged))
    _renumber(l)
    return True


def renumber_only(l, r):
    """change only the (unhashed-in-the-original-design) index field."""
    if len(l.entries) < 2:
        return False
    i = r.randrange(len(l.entries))
    l.entries[i].index = l.entries[i].index + 7
    return True


def truncate_tail(l, r):
    if len(l.entries) < 2:
        return False
    del l.entries[-1]
    return True


def edit_rechain(l, r):
    i = r.randrange(len(l.entries))
    l.entries[i].payload["content"] += " [edited]"
    _rechain(l, i)
    return True


def delete_rechain(l, r):
    if len(l.entries) < 2:
        return False
    i = r.randrange(len(l.entries))
    del l.entries[i]
    _rechain(l, min(i, len(l.entries) - 1) if l.entries else 0)
    return True


TAMPERS = {
    "edit_content": edit_content,
    "edit_agent": edit_agent,
    "edit_tool_result": edit_tool_result,
    "edit_provenance_link": edit_provenance_link,
    "edit_last_entry": edit_last_entry,
    "delete_middle": delete_middle,
    "delete_first": delete_first,
    "reorder_swap": reorder_swap,
    "insert_forged": insert_forged,
    "renumber_only": renumber_only,
    "truncate_tail": truncate_tail,
    "edit_rechain": edit_rechain,
    "delete_rechain": delete_rechain,
}


def _detect(ledger: IntegrityLedger, head: str, length: int) -> dict[str, bool]:
    chain_ok, _ = ledger.verify()
    graph_ok, _ = verify_with_anchor(ledger)  # chain + graph, no anchor
    anch_ok, _ = verify_with_anchor(ledger, head, length)
    return {"chain": not chain_ok, "chain+graph": not graph_ok, "anchored": not anch_ok}


def _overhead(runs, repeats: int = 20) -> dict[str, float]:
    n_events = sum(len(r.events) for r in runs)
    t0 = time.perf_counter()
    ledgers = []
    for _ in range(repeats):
        ledgers = [build_provenance_ledger(r) for r in runs]
    build = (time.perf_counter() - t0) / repeats
    t0 = time.perf_counter()
    for _ in range(repeats):
        for l in ledgers:
            verify_with_anchor(l, l.head_hash, len(l.entries))
    verify = (time.perf_counter() - t0) / repeats
    return {
        "events": n_events,
        "append_ms_per_event": build / n_events * 1000,
        "verify_ms_per_event": verify / n_events * 1000,
        "target_ms_per_event": 10.0,
    }


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--logs", nargs="+", default=None, help="synthetic log dirs (default: sample_logs + injected_violations when no real root is given)")
    ap.add_argument("--real-whowhen-root", default=None, help="real Who&When release (Hand-Crafted + Algorithm-Generated); all 184 logs")
    ap.add_argument("--limit", type=int, default=None)
    ap.add_argument("--reps", type=int, default=1, help="tamper attempts per (run, tamper type)")
    ap.add_argument("--seed", type=int, default=0)
    ap.add_argument("--out", default="results/tamper_results.json")
    args = ap.parse_args()

    runs = []
    log_dirs = args.logs if args.logs is not None else ([] if args.real_whowhen_root else ["data/sample_logs", "data/injected_violations"])
    for d in log_dirs:
        runs.extend(load_logs_from_dir(ROOT / d if not Path(d).is_absolute() else d))
    if args.real_whowhen_root:
        runs.extend(load_whowhen_release_full(args.real_whowhen_root, args.limit))
    print(f"Loaded {len(runs)} clean runs")
    rng = random.Random(args.seed)

    # false alarms on clean ledgers (fresh build, and after a deepcopy round-trip)
    false_alarms = {"chain": 0, "chain+graph": 0, "anchored": 0}
    for run in runs:
        l = build_provenance_ledger(run)
        det = _detect(copy.deepcopy(l), l.head_hash, len(l.entries))
        for k, v in det.items():
            false_alarms[k] += int(v)

    per_type = {t: {"applied": 0, **{m: 0 for m in ("chain", "chain+graph", "anchored")}} for t in TAMPERS}
    for run in runs:
        for _ in range(args.reps):
            for name, fn in TAMPERS.items():
                clean = build_provenance_ledger(run)
                head, length = clean.head_hash, len(clean.entries)
                tampered = copy.deepcopy(clean)
                if not fn(tampered, rng):
                    continue
                per_type[name]["applied"] += 1
                for m, hit in _detect(tampered, head, length).items():
                    per_type[name][m] += int(hit)

    total = sum(v["applied"] for v in per_type.values())
    summary = {}
    for m in ("chain", "chain+graph", "anchored"):
        summary[m] = {
            "detected": sum(v[m] for v in per_type.values()),
            "detection_rate": sum(v[m] for v in per_type.values()) / total,
            "false_alarms": false_alarms[m],
            "false_alarm_rate": false_alarms[m] / len(runs),
        }
    overhead = _overhead(runs, repeats=3 if args.real_whowhen_root else 20)

    result = {
        "n_clean_runs": len(runs),
        "n_tamper_cases": total,
        "seed": args.seed,
        "data": "real Who&When release" if args.real_whowhen_root else "synthetic (sample_logs + injected_violations)",
        "total_events": overhead["events"],
        "summary_by_mode": summary,
        "per_tamper_type": per_type,
        "overhead": overhead,
        "note": (
            "synthetic, deterministic tampering applied to the logs. Unanchored chain detection of "
            "truncate_tail / *_rechain is impossible by construction; only the anchored mode catches them."
        ),
    }
    out = ROOT / args.out
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(result, indent=2), encoding="utf-8")

    print(f"\n{total} tamper cases over {len(runs)} runs")
    print(f"{'type':<22}{'n':>5}{'chain':>8}{'+graph':>8}{'anchored':>10}")
    for t, v in per_type.items():
        print(f"{t:<22}{v['applied']:>5}{v['chain']:>8}{v['chain+graph']:>8}{v['anchored']:>10}")
    for m, s in summary.items():
        print(f"{m:<12} detection {s['detection_rate']:.1%}  false alarms {s['false_alarms']}/{len(runs)}")
    print(f"overhead: append {overhead['append_ms_per_event']:.4f} ms/event, verify {overhead['verify_ms_per_event']:.4f} ms/event")
    print(f"Wrote {out}")


if __name__ == "__main__":
    main()
