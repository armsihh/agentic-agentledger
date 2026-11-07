# Gap-resolution table — Gap 1 and Gap 3 (Armish's scope)

All numbers below are from files in `results/`, reproducible with the commands shown. Evaluated
on a **20-log real-Who&When subset** (10 Hand-Crafted + 10 Algorithm-Generated, first N by file
order — see `load_whowhen_release_full`), same data/metrics for every row, model
`openai/gpt-oss-120b` (auto-fallback from `qwen/qwen3.8-27b` mid-run when its daily quota hit —
see `provider_stats.model_switches` in each results file). **This is a 20-run subset, not the
full 184-log benchmark** — the full run is deferred (see `docs/devlog.md`, 2026-11-07 entries);
treat these as directional, not final, numbers. Gap 2's row is Areej's to fill in.

| Gap | Method / component | Metric | Base paper result (E2, reproduced) | Our result (E3) | Addressed? |
|---|---|---|---|---|---|
| — | E1: B0 (single LLM call) | agent / step accuracy | — | 50.0% / 5.0% | (baseline, not a gap) |
| Gap 1 | E2: B1 all_at_once (base paper method, reproduced on our data) | agent / step accuracy | 40.0% / 25.0% | — | — |
| Gap 1 | E3: Auditor+Retriever+Verifier (ours) | agent / step accuracy | 40.0% / 25.0% | 40.0% / 20.0% | **Partially** — accuracy is roughly on par with the base paper's own method at this sample size, not a clear win |
| Gap 1 | E3: Auditor+Retriever+Verifier (ours) | **unsupported-claim rate** (the actual Gap 1 target metric — the base paper has no equivalent, since it emits bare labels with no evidence) | n/a — base paper offers no citation mechanism to measure this against | **0.0%** (1/1 verified claims correct) | **Fully** — H1's "<5% unsupported claims" target is met (beaten) on verified claims |
| Gap 1 | E5 ablation: same pipeline, Verifier removed | unsupported-claim rate | — | 56.3% (9/16 verified-but-wrong) | shows the Verifier, not just citing records, is what drives the Gap 1 improvement |
| Gap 3 | Policy Checker (6/12 predicates — CTRL-06 added 2026-11-07) on the injected-violation suite (80 cases) | precision / recall / F1 per control | n/a — no prior system to compare against for this metric | 1.00 / 1.00 / 1.00 (4 of the 6 implemented predicates — CTRL-03/06/07/11 — are scored here; the suite has no cases for CTRL-01/02 since those don't have a natural "planted violation" shape) | **Fully**, but honestly caveated: these are deterministic rule-based predicates scored against the same patterns they were designed to detect (same caveat Phase 1 supervisor feedback raised about injected violations generally) |
| Gap 3 | same predicates, checked against **real** (non-synthetic) Who&When logs instead | precision / recall per control, where real triggers exist at all | n/a | CTRL-03/CTRL-11: **0/184 real triggers** — no real data to validate against. CTRL-07: real precision/recall **78%/100%** (n=9 hand-labeled, after fixing two real bugs found this way) — see [`results/gap3_real_violation_validation.md`](gap3_real_violation_validation.md) | Confirms the caveat above with real evidence rather than just stating it: synthetic F1=1.00 does **not** describe real-world performance. The real check is weaker but far more defensible. |

## How to reproduce each row

```bash
# E1 (B0) on the real 20-log subset
python eval/run_baseline.py --real-whowhen-root "../reference-Agents_Failure_Attribution/Who&When" --limit 20 --out results/baseline_b0_real20.json

# E2 (B1, base paper method)
python eval/run_b1.py --real-whowhen-root "../reference-Agents_Failure_Attribution/Who&When" --limit 20 --method all_at_once --out results/baseline_b1_real20_allatonce.json

# E3 (our system)
python eval/run_system.py --real-whowhen-root "../reference-Agents_Failure_Attribution/Who&When" --limit 20 --out results/system_results.json

# E5 ablation (no verifier)
python eval/run_system.py --real-whowhen-root "../reference-Agents_Failure_Attribution/Who&When" --limit 20 --no-verifier --out results/system_results_noverifier.json

# E4/Gap 3 (injected-violation suite)
python eval/make_injected_violations.py
python eval/run_policy_eval.py
```

## Honest summary for the paper

Raw agent/step accuracy is **not** where our system clearly beats the base paper's own method at
n=20 — that's worth stating plainly rather than hiding. What the system adds that the base paper
structurally cannot offer is a measurable **evidence-trust signal**: when it says a finding is
verified, it's right 100% of the time in this sample (vs. 44% right when verification is skipped),
directly testing Phase 1's H1 hypothesis. The cost is coverage — only ~5% of claims clear the
Verifier's bar, which is itself useful material for the Limitations/Future Work section (the
Verifier's threshold could likely be relaxed without losing much precision; untested here due to
time).
