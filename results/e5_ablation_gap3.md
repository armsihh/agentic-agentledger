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
| **With Policy Checker** (`results/gap3_policy_eval.json`) | CTRL-03, CTRL-07, CTRL-11 | precision = recall = F1 = **1.00** on all 30 injected-violation cases (10 clean + 10 violating per control) |
| **Without Policy Checker** | none | 0 violations ever detected — every run is reported as "no control findings," including the 15 runs that have a planted violation |

So removing the Policy Checker costs 100% of Gap 3's detection capability by construction (it's
the only component that runs control predicates at all) — the more informative number is the
**with-Policy-Checker** column itself, and the honest caveat that goes with it: these are
deterministic trigger/predicate rules (CTRL-03: high-risk tool call without a prior approval
signal; CTRL-07: an error step with no later corrective-action signal; CTRL-11: a sensitive
argument key in a tool call) scored against the exact patterns they were written to detect, which
is the same "injected violations may be easier to catch than real ones" limitation the Phase 1
supervisor feedback raised. **We have not yet validated these predicates against a human-labelled
sample of real (non-synthetic) violations** — that validation is explicitly out of scope for this
pass given the time available, and is the clearest next step for Gap 3 future work.

Reproduce: `python eval/make_injected_violations.py && python eval/run_policy_eval.py`
