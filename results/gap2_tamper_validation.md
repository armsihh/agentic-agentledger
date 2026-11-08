# Gap 2 — tamper-evident ledger + provenance graph: E4 results and honest caveats

## Primary result: all 184 real Who&When logs

Source: `results/tamper_results_real184.json`. Reproduce (no LLM calls, seed 0):
`python eval/run_tamper_test.py --real-whowhen-root "../reference-Agents_Failure_Attribution/Who&When" --reps 3 --out results/tamper_results_real184.json`.
Data: 184 real logs (58 Hand-Crafted + 126 Algorithm-Generated, 4,092 events); each of 13 tamper types applied
3x per log = 6,624 applicable cases (`edit_tool_result` is N/A: the real release has no tool calls).

| Verification mode | Detection | False alarms (clean) |
|---|---|---|
| bare hash chain | 75.0% | 0 / 184 |
| chain + provenance-graph consistency | 82.5% | 0 / 184 |
| chain + graph + external anchor (head hash + length) | **100.0%** | 0 / 184 |

Overhead: ~0.052 ms/event append + ~0.051 ms/event verify (~0.10 ms total), ~100x under the 10 ms target.
The tamper *injection* is still synthetic (we edit real logs, no real attacker), see caveats below. The
synthetic-log run (83 short logs) is kept as a secondary check in `tamper_results.json`; its section follows.


### Per-tamper-type results (real data: 184 logs, 3 attempts per log per type)

Source: `results/tamper_results_real184.json`. Each cell is caught / applied.

| Tamper check | What the attacker does | Bare chain | Chain + graph | Anchored |
|---|---|---|---|---|
| `edit_content` | change a message's text | 552/552 (100%) | 552/552 (100%) | 552/552 (100%) |
| `edit_agent` | change which agent wrote an entry | 552/552 (100%) | 552/552 (100%) | 552/552 (100%) |
| `edit_tool_result` | forge a tool call's result (N/A on real logs: no tool calls) | N/A | N/A | N/A |
| `edit_provenance_link` | rewrite a provenance link (attributed_to) | 552/552 (100%) | 552/552 (100%) | 552/552 (100%) |
| `edit_last_entry` | edit the final entry | 552/552 (100%) | 552/552 (100%) | 552/552 (100%) |
| `delete_middle` | remove an entry from the middle | 552/552 (100%) | 552/552 (100%) | 552/552 (100%) |
| `delete_first` | remove the first entry | 552/552 (100%) | 552/552 (100%) | 552/552 (100%) |
| `reorder_swap` | swap two adjacent entries | 552/552 (100%) | 552/552 (100%) | 552/552 (100%) |
| `insert_forged` | insert a forged entry | 552/552 (100%) | 552/552 (100%) | 552/552 (100%) |
| `renumber_only` | change only the entry's index field | 552/552 (100%) | 552/552 (100%) | 552/552 (100%) |
| `truncate_tail` | delete the last entry (chain still valid) | 0/552 (0%) | 0/552 (0%) | 552/552 (100%) |
| `edit_rechain` | edit an entry, then recompute every later hash | 0/552 (0%) | 0/552 (0%) | 552/552 (100%) |
| `delete_rechain` | delete an entry, then recompute every later hash | 0/552 (0%) | 499/552 (90%) | 552/552 (100%) |

Reading the table: nine checks are caught by the bare chain every time (the N/A row isn't counted). The last three (truncation and the two re-hash attacks) are invisible to it by construction; the graph catches some `delete_rechain` cases because a deleted entry leaves a dangling `wasDerivedFrom` link, and only the external anchor catches all of them.

---

## Secondary: synthetic logs (sample_logs + injected_violations)

Source: `results/tamper_results.json` (reproduce: `python eval/run_tamper_test.py`, seed 0, no LLM calls).
Data: 83 clean runs (3 `data/sample_logs` + 80 `data/injected_violations`), 1–5 events each; 779 injected
tamper cases across 13 tamper types; each clean ledger also verified untouched to measure false alarms.

| Verification mode | Detection | False alarms (clean) |
|---|---|---|
| bare hash chain (`IntegrityLedger.verify`) | 78.3% | 0 / 83 |
| chain + provenance-graph consistency | 81.6% | 0 / 83 |
| chain + graph + external anchor (head hash + length) | **100.0%** | 0 / 83 |

Overhead: ~0.032 ms/event to append (hash + provenance links), ~0.026 ms/event to verify — roughly
200x under Phase 1's 10 ms/event target.

Per-type detail (n applied → bare chain / chain+graph / anchored) is in the JSON. The undetected-without-anchor types:

- `truncate_tail` (delete last entry): a hash chain cannot see a missing tail — 0% unanchored, 100% anchored.
- `edit_rechain` (attacker edits then recomputes every later hash): 0% unanchored by construction.
- `delete_rechain`: 0% by chain, 60% by graph consistency (a broken `wasDerivedFrom` link), 100% anchored.

## Honest reading

- **The headline 100% is only true with an external anchor.** Truncation and a full re-hash are invisible
  to the chain alone; the anchor (head hash + length stored where the attacker can't rewrite it) does that work,
  not the hash chain or the provenance graph. Without it the honest number is 78.3%.
- **Most tamper types are trivially detectable** (any payload edit/deletion/reorder breaks a SHA-256 chain) —
  expect ~100% there. The tampering is synthetic and was written by the same author as the detector, on short
  logs, so this is a correctness check, not evidence about a real adversary.
- **Two real defects found by the harness and fixed:**
  1. `eval/run_system.py:_build_ledger` hashes only `event_id`, `agent`, `tool_calls` — an edit to a message's
     *content* would not break that chain. `provenance.build_provenance_ledger` hashes the full event; that
     builder is what this harness tests. (`run_system.py` is left unchanged; Armish's pipeline still uses the
     narrower payload.)
  2. `LedgerEntry.index` is not part of the hash, so index-only edits passed `verify()` (0/43 detected before;
     see `results/tamper_results_before_index_fix.json`). `verify()` now checks index == position (43/43).
- The provenance graph is a *navigation/forensics* aid (lineage queries, structural checks); its links are
  protected because they sit inside the hashed payload, not because the graph adds detection power.
- Not tested: concurrent writers, storage-level attacks, real Who&When logs (not on this machine), and the
  security of the anchor itself.
