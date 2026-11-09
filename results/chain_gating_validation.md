# Does a broken ledger actually gate Gap 1 / Gap 3 findings? (E7)

Reviewer feedback on the paper draft: "the three components are fairly independent, and the
link between them (a broken chain forces `verified=False`) is never evaluated." This checks
that claim empirically, not just by reading `orchestrator.py`'s source.

Reproduce (no LLM calls -- `MockProvider`, deterministic, `seed=0`):
```
python eval/run_chain_gating_test.py --real-whowhen-root "../reference-Agents_Failure_Attribution/Who&When" --out results/chain_gating_results.json
```

## Setup

For each of the 20-log real Who&When subset (the same subset Gap 1's headline numbers use),
each of `run_tamper_test.py`'s 13 tamper types is applied once (240 applicable cases; the
real release has no tool calls, so `edit_tool_result` never applies). `run_system_with_trace()`
is then run on the tampered ledger and we check whether the Gap-1 finding and every Gap-3
control finding's `verified` flag actually reflects the tampering.

## Result

| | n | Gap-1 finding still `verified=True` | ≥1 Gap-3 control finding `verified=True` |
|---|---|---|---|
| Bare chain **detected** the tamper (9 of 13 types) | 180 | 0 | 0 |
| Bare chain **missed** the tamper (`truncate_tail`, `edit_rechain`, `delete_rechain`) | 60 | 0 | **60 / 60** |

**When the bare chain detects the tampering, the gate holds with zero exceptions**: `claim_verified
= result.verified and ledger_ok` and `verified=ledger_ok` (every control finding) correctly force
every finding to `verified=False`, across all 180 such cases. This is the first direct evidence
that the gate described in Section 4/Methodology is real and not just declared.

**But the gate is only as strong as `ledger.verify()`** — the bare chain — and
`results/gap2_tamper_validation.md` already showed the bare chain misses `truncate_tail` and
`edit_rechain` entirely (0% detection) and most `delete_rechain` cases, because
`orchestrator.py` calls the bare `ledger.verify()`, never `verify_with_anchor()`. In every one of
the 60 cases here where the bare chain missed a genuine tamper, at least one Gap-3 control
finding was reported `verified=True` on a log that had, in fact, been tampered with — Gap 3's
control findings trust the bare chain with no second check. Gap 1's own finding happened to stay
`verified=False` in all 60 of those cases too, but via the Verifier's independent judgment, not
the ledger gate — that's incidental (and provider-dependent), not a second line of defense by
design.

## Honest takeaway

The "a broken chain forces every finding to `verified=False`" claim is true and empirically
confirmed, but it should be read as "a chain the bare `verify()` call detects as broken," not
"any tampering." The one upgrade that would close this — gating on `verify_with_anchor()`
instead of `verify()` — is a one-line change in `orchestrator.py` not made in this project; it is
listed as future work. This result directly answers the coherence criticism: the link between
Gap 2 and Gaps 1/3 is real and tested, and its exact boundary is now known rather than assumed.
