# Failure analysis — Gap 1 (Auditor/Retriever/Verifier), 20-log real Who&When sample

Source: `results/system_results.json` (20-run real subset, model `openai/gpt-oss-120b` after
fallback from `qwen/qwen3.8-27b`). Categorized by hand from every run's prediction vs. ground
truth; counts below are exhaustive over the 20 runs, not cherry-picked.

## Failure categories and frequency

| Category | Count | Share |
|---|---|---|
| Correct abstention would be right, but we abstain on a real failure ("unknown") | 8/20 | 40% |
| Wrong agent, biased toward blaming the coordinating agent ("Orchestrator") | 3/20 | 15% |
| Correct agent, wrong decisive step | 4/20 | 20% |
| Fully correct (agent + step) | 4/20 | 20% |
| Infrastructure error (Groq rate-limited after all fallback models exhausted) | 1/20 | 5% |

(Separately: of the 4 fully-correct runs, **0 were marked `verified=True`** by the Verifier — see
the Verifier-calibration note below, which is the dominant limitation, not any single category
above.)

## Representative success cases

**Case 1 — `e142056d-56ab-4352-b091-b56054bd1359` (Algorithm-Generated, 5-event trajectory).**
Ground truth: `GameTheory_Expert`, step 1. Trajectory: `[0] AlgorithmDesign_Expert` hands off a
coin-distribution problem; `[1] GameTheory_Expert` works the solution and makes the actual
reasoning error; `[2] VerificationExpert` incorrectly agrees; `[4] VerificationExpert` says
`TERMINATE`. The Retriever's error-keyword search over a 5-event log surfaces step 1 directly
(short conversation, little to filter), the Auditor cites exactly `[...-1]`, and the prediction
matches ground truth exactly. **Note:** the Verifier still rejected this citation
(`verified=false`) despite the claim being correct — see the calibration note below.

**Case 2 — `42d4198c-5895-4f0a-b0c0-424a66465d83` (Algorithm-Generated, 9-event trajectory).**
Ground truth: `DataVerification_Expert`, step 3. Trajectory: `[2] Computer_terminal` returns a
successful script execution; `[3] DataVerification_Expert` misreads the output ("it seems like
there was an error or miscalculation") and introduces the actual mistake while "correcting" a
result that wasn't wrong. The Auditor correctly isolates step 3 and cites it. Again
`verified=false` despite being correct.

## Representative failure cases

**Case 1 — `d1af70ea-a9a4-421a-b9cc-94b5e02f1788` (Algorithm-Generated, 10-event trajectory),
category: incorrect abstention.** Ground truth: `Validation_Expert`, step 5 (reports fabricated
population figures without actually querying `data.census.gov`, despite claiming to). Our
system predicted `unknown` with zero citations. **Likely cause:** the Retriever's error-keyword
list (`error, fail, exception, incorrect, wrong, violat`) doesn't fire on this failure — the
mistake is a *plausible-sounding but unverified claim*, not a sentence containing an obvious
error word, so step 5 never made it into the candidate shortlist the Auditor was shown. **Fix for
future work:** the Retriever needs a second signal beyond error-keyword matching — e.g., flagging
steps that claim a data source without a preceding successful tool call to that source, which is
exactly the kind of check a citation-aware Auditor with access to the full tool-call ledger (not
just event text) could catch directly.

**Case 2 — `0a65cb96-cb6e-4a6a-8aae-c1084f613456` (Hand-Crafted, 93-event trajectory), category:
wrong agent, orchestrator bias.** Ground truth: `WebSurfer`, step 32. Our system predicted
`Orchestrator`, step 82. **Likely cause:** this is the longest trajectory in the sample (93
events); the Retriever's tail-window (last 4 events) and keyword search pulled mostly
`Orchestrator`-authored planning/ledger-update turns (the Orchestrator narrates "is_request_
satisfied" status after almost every step, so it dominates keyword hits on words like "not yet"),
while the actual `WebSurfer` misstep at step 32 is buried mid-trajectory and never retrieved.
**Fix for future work:** this is the same long-log problem TRAIL reports (Phase 1, A3.2 S1) and
that our Gap 1 proposal explicitly set out to address — the current Retriever's keyword+tail
heuristic is a first pass, not the smarter retrieval (embedding-based span index) the Phase 1
proposal's B8 architecture called for. On long logs it systematically favors whichever agent
talks most (the Orchestrator), not whichever agent made the decisive error.

## Verifier-calibration note (the dominant limitation)

Every one of the 4 fully-correct predictions in this sample was still marked `verified=false`.
Combined with the ablation study (`results/gap1_ablation_summary.json`: unsupported-claim rate
0% with the Verifier vs. 56% without it), the picture is consistent: **the Verifier has excellent
precision and very poor recall** — when it does say "verified," it's right, but it says so far too
rarely, rejecting good single-citation evidence that a human reviewer would likely accept. This is
the clearest, most actionable item for future work: loosen the Verifier's acceptance bar (e.g.,
accept a single clearly-relevant citation rather than demanding stronger corroboration) and
re-measure both metrics together, since there is an explicit precision/recall trade-off here that
hasn't been tuned.
