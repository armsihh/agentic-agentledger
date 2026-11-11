# E5 ablation — Gap 3 (Policy Checker)

Unlike Gap 1 (where removing the Verifier changes the Auditor's output), removing the Policy
Checker has **no effect on Gap 1's predictions** — it is a structurally separate, deterministic
step that runs over the ledgered trajectory and produces its own findings; `use_policy_checker`
only controls whether those findings are *attached to the report*, per
`src/agentledger/orchestrator.py`. Re-running the same Who&When logs with
`--no-policy-checker` would therefore reproduce identical agent/step predictions and just drop
the `control_findings` list to `[]` — not a meaningful new experiment.

The real ablation question for Gap 3 is **"how much compliance-detection capability does removing
the Policy Checker cost?"**, which is better answered on the injected-violation suite (where we
have planted ground truth) than on Who&When (which has none):

| Configuration | Controls checked | Detection capability |
|---|---|---|
| **With Policy Checker** (`results/gap3_policy_eval.json`) | CTRL-03, CTRL-06, CTRL-07, CTRL-11 | precision = recall = F1 = **1.00** on all 80 injected-violation cases (10 clean + 10 violating per control) |
| **Without Policy Checker** | none | 0 violations ever detected — every run is reported as "no control findings," including the 40 runs that have a planted violation |

So removing the Policy Checker costs 100% of Gap 3's detection capability by construction (it's
the only component that runs control predicates at all) — the more informative number is the
**with-Policy-Checker** column itself, and the honest caveat that goes with it: these are
deterministic trigger/predicate rules (CTRL-03: high-risk tool call without a prior approval
signal; CTRL-06: a tool call with no recorded outcome; CTRL-07: an error step with no later
corrective-action signal; CTRL-11: a sensitive argument key in a tool call) scored against the
exact patterns they were written to detect, which is the same "injected violations may be easier
to catch than real ones" limitation the Phase 1 supervisor feedback raised.

**Update 2026-11-07 (late):** that validation gap has since been closed for CTRL-03/07/11 —
see [`results/gap3_real_violation_validation.md`](gap3_real_violation_validation.md). Short
version: CTRL-03/CTRL-11 have zero real trigger occurrences in the real Who&When benchmark (no
real data exists to check them against at all), and CTRL-07's real precision/recall is 78%/100%
(n=9 hand-labeled), not 1.00/1.00 — a real, honest gap from the synthetic number above, not a
contradiction of it. CTRL-06 (added the same night as this validation pass) hasn't been
real-data validated yet.

Reproduce: `python eval/make_injected_violations.py && python eval/run_policy_eval.py`
