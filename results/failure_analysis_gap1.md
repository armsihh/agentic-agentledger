# Failure analysis — Gap 1 (Auditor/Retriever/Verifier), 20-log real Who&When sample

Source: `results/system_results.json` (20-run real subset, clean run with zero errors, model
`openai/gpt-oss-120b` after fallback from `qwen/qwen3.8-27b`). Categorized by hand from every
run's prediction vs. ground truth; counts below are exhaustive over the 20 runs, not
cherry-picked.

**Note on reproducibility:** an earlier pass of this experiment (archived as
`results/system_results_original_n19.json` / `results/gap1_ablation_summary_original_n19n16.json`)
produced materially different numbers — a 5% verified rate instead of 60%, and 0/4 fully-correct
predictions marked verified instead of 2/2. This is **not** purely sampling noise: the Verifier's
prompt was recalibrated between the two passes, from requiring cited records to "prove" the claim
to requiring only that they be "relevant and consistent" with it (`src/agentledger/agents/verifier.py`,
commit `219f5e7`), specifically because the first pass showed poor recall. That recalibrated prompt
was never run against live data until this run, so most of the 5%→60% jump reflects that
deliberate change, not chance. One genuine case of unrelated sampling variance remains: the
Auditor (unchanged between passes) predicted log `e142056d` correctly in one pass and incorrectly
in the other — see the Verifier-calibration note below and `docs/devlog.md`.

## Failure categories and frequency

| Category | Count | Share |
|---|---|---|
| Correct abstention would be right, but we abstain on a real failure ("unknown") | 7/20 | 35% |
| Wrong agent, biased toward blaming the tool-execution step ("Computer_terminal") | 5/20 | 25% |
| Wrong agent, other | 1/20 | 5% |
| Correct agent, wrong decisive step | 5/20 | 25% |
| Fully correct (agent + step) | 2/20 | 10% |
| Infrastructure error (Groq rate-limited after all fallback models exhausted) | 0/20 | 0% |

(Separately: of the 2 fully-correct runs, **both were marked `verified=True`** by the Verifier —
the Verifier is not simply rejecting good evidence. The dominant limitation is upstream of
acceptance; see the Computer_terminal-bias note below.)

## Representative success cases

**Case 1 — `42d4198c-5895-4f0a-b0c0-424a66465d83` (Algorithm-Generated, 9-event trajectory).**
Ground truth: `DataVerification_Expert`, step 3. Trajectory: `[2] Computer_terminal` returns a
successful script execution; `[3] DataVerification_Expert` misreads the output ("it seems like
there was an error or miscalculation") and introduces the actual mistake while "correcting" a
result that wasn't wrong. The Auditor correctly isolates step 3 and cites it, and the Verifier
accepts it (`verified=true`). This prediction is stable across both passes of this experiment.

**Case 2 — `df6561b2-7ee5-4540-baab-5095f742716a` (Algorithm-Generated, 8-event trajectory).**
Ground truth: `Verification_Expert`, step 4. Trajectory: `[3] Computer_terminal` reports
`exitcode: 124 (execution failed) ... Timeout`; `[4] Verification_Expert`, instead of retrying,
decides to simulate the needed numbers rather than actually computing them. The Auditor correctly
blames step 4, not the step-3 timeout that triggered it, and the Verifier accepts it. This shows
the pipeline *can* distinguish a reported error from an agent's bad response to it — just not
reliably, as the cases below show.

## Representative failure cases — the Computer_terminal bias

**5 of the 6 verified-but-wrong claims in this sample name the same agent, `Computer_terminal`,
as responsible.** `Computer_terminal` is the tool-execution role in these `autogen_magentic_one`
transcripts, not a reasoning agent — it only reports whether code ran, it doesn't decide what the
agents do. The pattern:

**Case 1 — `65afbc8a-89ca-4ad5-8d62-355bb401f61d`.** Ground truth: `AlgorithmDesign_Expert`, step
4. Trajectory: `[1] Computer_terminal` reports `exitcode: 1 (execution failed) ... indentation
error`; `[2] AlgorithmDesign_Expert` fixes it; `[3] Computer_terminal` reports
`exitcode: 0 (execution succeeded)`; `[4] AlgorithmDesign_Expert`'s *next* approach is the actual
decisive mistake. Our system cited step 1 and blamed `Computer_terminal` for an error that was
already resolved two steps earlier.

**Case 2 — `d1af70ea-a9a4-421a-b9cc-94b5e02f1788`.** Ground truth: `Validation_Expert`, step 5,
where the agent fabricates census figures without actually querying `data.census.gov` despite
claiming to — this step reads as confident, correct-sounding prose with no error-shaped language
at all. Our system instead cited step 6, where `Computer_terminal` reports an unrelated
`exitcode: 1` syntax error in a downstream calculation, and missed the fabrication entirely.

**Mechanism.** In both cases the cited record genuinely contains the word "error" or "failed", so
the Verifier's yes/no check ("do the cited records support this claim?") passes — it is a
textual-support check, not a causal one. The underlying cause sits one layer upstream, in the
Retriever: its error-keyword search (`error, fail, incorrect, wrong, exception, mistake, violat`)
reliably surfaces `Computer_terminal`'s raw stack traces (Python tracebacks literally contain
these words), so the terminal is over-represented in the candidate shortlist the Auditor ever
sees, regardless of whether it's actually at fault.

## Representative failure cases — incorrect abstention

**Case — `0a65cb96-cb6e-4a6a-8aae-c1084f613456` (Hand-Crafted, 93-event trajectory, the longest
in the sample).** Ground truth: `WebSurfer`, step 32 — a plain, uneventful "scrolled down one
page" screenshot report with no error-shaped language. Our system predicted `unknown` with zero
citations: the surrounding steps are dominated by `Orchestrator`-authored planning narration
(`"Updated Ledger... is_request_satisfied..."`), which doesn't trigger the error-keyword search
either, so step 32 never entered the Retriever's candidate shortlist. **This is the same log** as
an earlier pass of this experiment, which instead produced a confident wrong guess (blaming
`Orchestrator`, step 82) — same root cause (long log, no error-shaped language at the real
decisive step), different symptom (abstention vs. misattribution) across runs. This is the same
long-log problem TRAIL reports (Phase 1, A3.2 S1): the current Retriever's keyword+tail heuristic
is a first pass, not the smarter retrieval (embedding-based span index) the Phase 1 proposal's B8
architecture called for.

## Verifier-calibration note (the dominant limitation)

The Verifier's acceptance bar was already loosened once (see the reproducibility note above),
and that fix worked as intended: in this run both fully-correct predictions were accepted, so the
Verifier's weakness is no longer recall. It is causal judgment: the Verifier accepts a citation whenever the cited text is textually
error-shaped, without judging whether the cited agent is the one actually responsible. Combined
with the ablation study (`results/gap1_ablation_summary.json`: unsupported-claim rate 50% with
the Verifier vs. 65% without it), the picture is: the Verifier still helps, but mostly by
filtering out claims with no citation at all or a citation to a nonexistent record, not by
catching misattribution.

**Tested fix: causal-judgment Verifier prompt.** We implemented and ran the natural fix —
`src/agentledger/agents/verifier.py`'s `causal=True` path, invoked via
`eval/run_system.py --causal-verifier` — which asks the Verifier to judge whether the cited agent
actually *caused* the failure, not just whether the citation contains error-shaped text. Result on
the same 20 real logs (`results/system_results_causal_verifier.json`): unsupported-claim rate fell
from 50% to 40%, and 4 of the 5 original Computer_terminal-bias cases (`cf106601`, `f2feb6a4`,
`5d0080cb`, `65afbc8a`) were correctly rejected instead of falsely verified. But it is a real
trade-off, not a clean fix: verified rate collapsed from 60% to 25% (5/20 claims verified, down
from 12/20), agent accuracy fell from 35% to 30% and step accuracy from 10% to 5%, because the
stricter prompt triggers the Auditor's revision loop far more often and a revision is not
reliably better than the original claim. One bias case (`d1af70ea`) persisted even under the
causal prompt, and a previously stable, fully-correct, verified log (`df6561b2`) flipped to a
*new* incorrect Computer_terminal claim after revision. Future work: apply the causal check
selectively (e.g. only to citations of tool-execution steps) rather than to every claim, to try
to recover the coverage loss without losing the precision gain.
