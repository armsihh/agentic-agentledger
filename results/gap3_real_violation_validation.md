# Gap 3 validation against real (non-synthetic) data

The injected-violation suite (`results/e5_ablation_gap3.md`) scores CTRL-03/07/11 at a clean
1.00/1.00/1.00 — but, as already flagged there, that's deterministic rules scored against the
exact patterns they were designed to detect. This write-up is the real-data check that finding
needed: does any of this hold up against genuine agent logs, not planted cases? Short answer:
**partially, and the gap between "synthetic F1=1.00" and "real behaviour" is itself the finding.**

Method: scanned all 184 real Who&When logs (`../reference-Agents_Failure_Attribution/Who&When`)
for each control's trigger condition; where real triggers exist, hand-labeled a reproducible
random sample (`random.seed(42)`) against genuine human judgment of "did this actually happen,"
not the predicate's own output.

## CTRL-03 and CTRL-11: zero real triggers

```
runs with a high-risk tool call (CTRL-03 trigger):        0 / 184
runs with a sensitive-looking arg key (CTRL-11 trigger):  0 / 184
```

Neither control's trigger condition occurs *once* across the real benchmark — these Who&When
tasks are reasoning/search/code tasks, not ones that call `delete`/`pay`/`transfer`-style tools
or pass password-shaped arguments. **These two predicates can only be meaningfully evaluated on
the synthetic injected-violation suite; there is no real data to validate them against in this
benchmark at all.** That's a real limitation of the *benchmark* for this purpose, not a flaw we
can fix by trying harder — worth stating plainly in Limitations rather than implying both
controls got the same kind of real-world check CTRL-07 did.

## CTRL-07: 145/184 real logs trigger it — and a real bug was found

Hand-building the labeling sample surfaced a genuine false-positive source before any labeling
even started: `autogen_magentic_one` (the framework Who&When's logs were generated with) appends
a benign `UserWarning: ...Model mapping may be incorrect` line to many events — unrelated to
whether the task failed.

```
58 / 184 real runs contain this exact warning string
13 / 184 runs have it as their ONLY error-keyword trigger -- CTRL-07 fired on these purely
          because of harness logging noise, not any real problem
```

### Hand-labeled sample (n=16: 8 predicted-pass, 8 predicted-fail, seed=42)

| idx | predicate (before fix) | human judgment | verdict |
|---|---|---|---|
| 60 | PASS | genuine workaround after a timeout | TP |
| 23 | PASS | **spurious** — the "error" was the framework warning; task never failed | spurious trigger |
| 97 | PASS | genuine fix (`NameError` → corrected script) | TP |
| 93 | PASS | genuine fix (bad code-block formatting → reformatted, ran) | TP |
| 84 | PASS | code crashed (`TypeError`) and was never actually re-run — agents just asserted an answer was "correct" without fixing/verifying it | **FP** |
| 62 | PASS | genuine fix (implausible result → corrected script, plausible result) | TP |
| 57 | PASS | **spurious** — "error"/"fixed" both came from a GitHub issue *about* a bug the agents were reading, not their own failure | spurious trigger |
| 109 | PASS | a correction was genuinely attempted (predicate's own definition is "signal present," not "confirmed resolved") | TP |
| 164 | FAIL | real fix ("let's try again by importing...") — missed because "try again" wasn't in the keyword list | **FN** |
| 94 | FAIL | real fix, but stated in the *same* message as the error — missed because the old check only looked strictly later | **FN** |
| 12 | FAIL | genuine no-recovery (a "root cause of failure" postmortem, task abandoned) | TN |
| 122 | FAIL | ambiguous — agents switched strategy instead of fixing the actual bug; defensible either way | ambiguous |
| 69 | FAIL | **spurious** — "error" came from the task's own instructions ("...correct any errors"), not a report of one happening | spurious trigger |
| 5 | FAIL | **spurious** — framework warning, and it's the last step, so nothing could follow it anyway | spurious trigger |
| 3 | FAIL | **spurious** — same framework warning | spurious trigger |
| 29 | FAIL | genuine no-recovery (search obstacles, no resolution signal found) | TN |

5/16 triggers were spurious (framework noise or task-instruction text, not a real event) —
consistent with the 13/184 figure above plus a second, distinct noise source (task-instruction
wording). Of the 11 genuine cases: **precision 83% (5/6), recall 71% (5/7)** before any fix —
real numbers, not 1.00/1.00.

### Fix applied (`src/agentledger/controls.py`)

1. Strip the known framework-warning string before error-keyword matching.
2. Broaden `_CORRECTIVE_WORDS` to include "try again" / "reformat" / "redo" (natural phrasing
   that real transcripts actually use, which the original list missed).
3. Allow a corrective signal in the *same* step as the error, not only strictly later ones (an
   agent that notices and fixes something in one message was invisible to the old check).

### Re-measured after the fix

Full-184 distribution shift:

| | vacuous (no error) | pass (corrected) | fail (not corrected) |
|---|---|---|---|
| before | 39 | 38 | 107 |
| after | 52 | 93 | 39 |

The +13 vacuous runs are exactly the 13 that were only ever triggered by the framework warning —
confirms fix #1 worked as intended, not just a plausible-looking number.

Re-labeling the same 16-case sample: both false negatives (164, 94) now correctly flag as PASS.
But the same-step change also introduced a **new** false positive (idx 12): its error step is
a long planning paragraph that happens to also contain the word "correctly" elsewhere in the
*same* message, discussing a future step, not reporting a fix. Honest result on the 9 genuine,
non-ambiguous cases: **precision 78% (7/9), recall 100% (7/7)** — recall improved a lot, precision
dropped slightly. A real trade-off, not a strict win, from broadening the rule — the same shape
of finding as the Gap 1 Verifier's own precision/recall trade-off elsewhere in this project.

### Residual, unfixed limitations (found, not hidden)

- **idx 57 / idx 84-style confusion is not fixable with keyword matching alone.** Telling "the
  agent read about someone else's bug and fix" apart from "the agent had its own bug and fixed
  it," or "we asserted this is correct" apart from "we verified a fix actually worked," needs
  semantic judgment a keyword rule structurally cannot do — this is the same gap citation+
  verification was built to close for Gap 1's Auditor, and arguably Gap 3 would benefit from the
  same pattern (an LLM judge re-reading the cited steps) rather than more keyword patching.
- **idx 69-style task-instruction false triggers** (the word "error" appearing in what the task
  *asks* the agent to do, not in a report that something went wrong) aren't addressed by the
  framework-noise fix, since there's no single fixed string to strip — this would need
  distinguishing instruction text from narrative text structurally, not just more keywords.
- **Sample size is small** (n=16, n=11/9 genuine cases) — these precision/recall numbers are
  illustrative of a real, found trade-off, not statistically robust estimates. Treat them the
  same way the rest of this project treats its n=20 numbers: directional, not final.

## Takeaway for the paper

Don't carry the synthetic suite's 1.00/1.00/1.00 into the paper as if it describes real-world
performance. The honest version: CTRL-03/CTRL-11 have **no real data in this benchmark to
validate against at all**; CTRL-07, checked against real logs, found and fixed two real bugs
(recall 71%→100%) at a small precision cost (83%→78%), plus a measurable false-positive source
from the benchmark's own generation framework (13/184 runs) that's now filtered out. That's a
weaker-sounding headline than F1=1.00, and a far more defensible one.
