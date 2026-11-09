# Gap-resolution table — Gap 1 and Gap 3 (Armish's scope)

All numbers below are from files in `results/`, reproducible with the commands shown. Evaluated
on a **20-log real-Who&When subset** (10 Hand-Crafted + 10 Algorithm-Generated, first N by file
order — see `load_whowhen_release_full`), same data/metrics for every row, model
`openai/gpt-oss-120b` (auto-fallback from `qwen/qwen3.8-27b` mid-run when its daily quota hit —
see `provider_stats.model_switches` in each results file). **This is a 20-run subset, not the
full 184-log benchmark** — the full run is deferred (see `docs/devlog.md`, 2026-11-07 entries);
treat these as directional, not final, numbers. Gap 2's row is Areej's to fill in.

**Reproducibility note:** this table reflects a clean, evenly-paired rerun (20/20 runs, zero
errors, both the Verifier-on and Verifier-off conditions). An earlier pass produced a 0.0%/56.3%
unsupported-claim split instead of the 50.0%/65.0% below — archived as
`results/system_results_original_n19.json` / `results/system_results_noverifier_original_n16.json`
— evaluated over an uneven 19/16 sample after transient free-tier rate-limit errors, **and with a
stricter Verifier prompt** than the one in `src/agentledger/agents/verifier.py` today. The Verifier
was recalibrated (commit `219f5e7`, "require the cited records to be relevant and consistent"
rather than "prove the claim") specifically because that first pass showed poor recall, but the
recalibration was never run against live data until the rerun below — so most of this swing is a
real, intended effect of that change, not sampling noise. See `results/failure_analysis_gap1.md`
for the mechanism (a systematic Computer_terminal attribution bias) that explains most of the
remaining 50.0%, and for the one genuine case of run-to-run sampling variance that is unrelated
to the Verifier change.

| Gap | Method / component | Metric | Base paper result (E2, reproduced) | Our result (E3) | Addressed? |
|---|---|---|---|---|---|
| — | E1: B0 (single LLM call, whole log) | agent / step accuracy | — | 50.0% / 5.0% | (baseline, not a gap) |
| — | B2: non-agentic RAG audit (retrieve once, summarise once — no Verifier, ledger gate or Policy Checker) | agent / step accuracy | — | 25.0% / 0.0% (n=19, 1 run errored) | (baseline, not a gap — isolates what retrieval alone buys vs. B0, and what the Verifier/revision loop then buys vs. E3) |
| Gap 1 | E2: B1 all_at_once (base paper method, reproduced on our data) | agent / step accuracy | 40.0% / 25.0% | — | — |
| Gap 1 | E3: Auditor+Retriever+Verifier (ours) | agent / step accuracy | 40.0% / 25.0% | 35.0% / 10.0% | **No** — our system trails the base paper's own method at this sample size |
| Gap 1 | E3: Auditor+Retriever+Verifier (ours) | **unsupported-claim rate** (the actual Gap 1 target metric — the base paper has no equivalent, since it emits bare labels with no evidence) | n/a — base paper offers no citation mechanism to measure this against | **50.0%** (6/12 verified claims correct) | **Partially** — reduced from the no-verifier baseline, but far short of H1's "<5%" target; 5 of the 6 remaining unsupported claims share one identified cause (Computer_terminal attribution bias, see `failure_analysis_gap1.md`) |
| Gap 1 | E5 ablation: same pipeline, Verifier removed | unsupported-claim rate | — | 65.0% (13/20 verified-but-wrong) | shows the Verifier still reduces unsupported claims (65.0%→50.0%), just much less than an earlier, smaller-sample pass suggested |
| Gap 1 | **E8 ablation: selective causal-judgment Verifier** (causal prompt only for citations naming a tool-execution agent) | agent / step accuracy / unsupported-claim rate | 40.0% / 25.0% / n/a | **55.0% / 15.0% / 33.3%** | **Directionally yes, not statistically significant** — beats B1 on agent accuracy (the only configuration in this project to do so) and improves every Gap 1 metric over the default (E3), but Fisher's exact test gives p≈0.53 vs. B1 and p≈0.45 vs. the default — same caveat as the main H1 result (p≈0.47); see `failure_analysis_gap1.md` for per-case detail, the significance check, and the all-claims variant it was chosen over |
| Gap 3 | Policy Checker (6/12 predicates — CTRL-06 added 2026-11-07) on the injected-violation suite (80 cases) | precision / recall / F1 per control | n/a — no prior system to compare against for this metric | 1.00 / 1.00 / 1.00 (4 of the 6 implemented predicates — CTRL-03/06/07/11 — are scored here; the suite has no cases for CTRL-01/02 since those don't have a natural "planted violation" shape) | **Fully**, but honestly caveated: these are deterministic rule-based predicates scored against the same patterns they were designed to detect (same caveat Phase 1 supervisor feedback raised about injected violations generally) |
| Gap 3 | same predicates, checked against **real** (non-synthetic) Who&When logs instead | precision / recall per control, where real triggers exist at all | n/a | CTRL-03/CTRL-11: **0/184 real triggers** — no real data to validate against. CTRL-07: real precision/recall **78%/100%** (n=9 hand-labeled, after fixing two real bugs found this way) — see [`results/gap3_real_violation_validation.md`](gap3_real_violation_validation.md) | Confirms the caveat above with real evidence rather than just stating it: synthetic F1=1.00 does **not** describe real-world performance. The real check is weaker but far more defensible. |

## How to reproduce each row

```bash
# E1 (B0) on the real 20-log subset
python eval/run_baseline.py --real-whowhen-root "../reference-Agents_Failure_Attribution/Who&When" --limit 20 --out results/baseline_b0_real20.json

# E2 (B1, base paper method)
python eval/run_b1.py --real-whowhen-root "../reference-Agents_Failure_Attribution/Who&When" --limit 20 --method all_at_once --out results/baseline_b1_real20_allatonce.json

# B2 (non-agentic RAG audit)
python eval/run_b2.py --real-whowhen-root "../reference-Agents_Failure_Attribution/Who&When" --limit 20 --out results/baseline_b2_real20.json

# E3 (our system)
python eval/run_system.py --real-whowhen-root "../reference-Agents_Failure_Attribution/Who&When" --limit 20 --out results/system_results.json

# E5 ablation (no verifier)
python eval/run_system.py --real-whowhen-root "../reference-Agents_Failure_Attribution/Who&When" --limit 20 --no-verifier --out results/system_results_noverifier.json

# Causal-Verifier ablations (tests the fix for the Computer_terminal bias below)
python eval/run_system.py --real-whowhen-root "../reference-Agents_Failure_Attribution/Who&When" --limit 20 --causal-verifier-mode all --out results/system_results_causal_verifier.json
python eval/run_system.py --real-whowhen-root "../reference-Agents_Failure_Attribution/Who&When" --limit 20 --causal-verifier-mode selective --out results/system_results_causal_selective.json

# E4/Gap 3 (injected-violation suite)
python eval/make_injected_violations.py
python eval/run_policy_eval.py
```

## Honest summary for the paper

Raw agent/step accuracy is **not** where our system beats the base paper's own method at n=20 —
our system actually trails it (35.0%/10.0% vs. 40.0%/25.0%), and that's worth stating plainly
rather than hiding. Retrieval alone (B2, no Verifier/ledger-gate/Policy Checker) scores even lower
(25.0%/0.0%) than either B0 (whole-log, 50.0%/5.0%) or E3 — a short candidate shortlist without
citation discipline or verification is not obviously better than reading the whole log, which is
itself useful material for the paper rather than an inconvenient number to omit. What the system
adds that neither baseline structurally can offer is a measurable **evidence-trust signal**: when
E3 says a finding is verified, it's right 50.0% of the time in this sample (vs. 35.0% right when
verification is skipped) — a real but modest improvement, not the clean win a smaller, earlier
pass of this experiment suggested. The cost is coverage — only 60% of claims clear the Verifier's
bar, down from 100% with no verification at all. The dominant remaining problem is not coverage
but causal judgment: 5 of 6 verified-but-wrong claims blame `Computer_terminal` (the
tool-execution role) for errors it only reports, because the Verifier checks whether a citation is
textually error-shaped, not whether the cited agent actually caused the failure. We tested the
direct fix — a Verifier prompt that judges causation instead of textual support — three ways.
Applied to every claim, it helps (unsupported-claim rate 50%→40%, 4/5 bias cases caught) but is
not a clean win (verified rate collapses 60%→25%, agent accuracy drops to 30%). Applied
**selectively** — causal judgment only for citations naming a tool-execution agent, lenient
prompt otherwise — it beats both the default and the all-claims variant on every metric: 55.0%
agent accuracy (beating B1's reproduced 40.0%, the first result in this project to do so), 15.0%
step accuracy, 75.0% verified rate, and 33.3% unsupported-claim rate — but, checked with the same
Fisher's exact test used for the main H1 result (p≈0.47), neither improvement reaches
significance at n=20 (p≈0.45 vs. the default, p≈0.53 vs. B1). Applying the same rigor to the
exciting number as to the disappointing one, not just to the latter, is the point. See
`results/failure_analysis_gap1.md` for the full comparison table, per-case detail, and all three
significance checks — this is still the strongest configuration found for Gap 1, worth
considering as the new default, but validate at larger n before leaning hard on "beats B1."
