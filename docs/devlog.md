# Development log

Dated entries, append-only. Each entry: what failed/was missing, what changed, measured effect.

## 2026-11-07 — Armish — Gap 1/3 agentic pipeline, first pass

- **Observed:** Phase 1 had no agentic Auditor; B0/B1 were single-shot, whole-log baselines
  only. Also, the free Who&When real-data evaluation (added this session) crashed after 12/184
  runs on Groq's free tier: `GroqProvider: rate-limited after repeated retries`, because calls
  were unpaced and the retry budget (6 attempts, max ~32s backoff) wasn't enough to ride out a
  sustained token-per-minute cap.
- **Change:** Built the Auditor (`agents/auditor.py`) + Retriever (`agents/retriever.py`) +
  Verifier (`agents/verifier.py`) loop and wired it through `orchestrator.run_system()`. The
  Retriever shortlists ~12 candidate records (error-keyword search + tail window) instead of
  reading the whole log, satisfying the Gap 1 "retrieval, not whole-log" design from Phase 1's
  B5. The Verifier re-reads only the cited records and rejects claims that don't hold up,
  revising once (per B8's "at most two revisions"). A broken ledger chain now forces
  `verified=False` regardless of what the Verifier says — Gap 2 is a real gate on Gap 1's output,
  not a side calculation.
  Also fixed the Groq rate-limit crash: added a 3s inter-call pacing delay and raised retries to
  10 with a 30s backoff cap, and made `run_b0`/`run_b1`/`run_system` skip a single run's
  exception instead of losing the whole batch's progress.
- **Effect:** `python -m pytest tests/` — 33/33 passing (was 18; added control + agent tests).
  Gap 3's injected-violation suite (30 synthetic cases: 10 each for CTRL-03/07/11) scores
  precision=recall=F1=1.00 per control — expected for now since these are deterministic
  trigger/predicate rules written to detect exactly the patterns planted; this is the same
  "injected violations may be easier to catch than real ones" caveat the Phase 1 supervisor
  feedback flagged, carried forward honestly rather than hidden.
- **Still open:** E3 (system) real-Who&When run not yet executed (queued behind the B0/B1 real
  runs on the shared Groq account to avoid doubling rate-limit contention). CTRL-04/05/06/08/09/10/12
  remain declared-but-unimplemented — out of scope for this pass given the timeline; the Policy
  Checker already skips them rather than silently passing them.

## 2026-11-07 — Armish — Diagnosed a 30-minute "hang", ran real E3

- **Observed:** `eval/run_system.py` on 20 real Who&When logs appeared to hang for 30+ minutes
  with no progress. Isolated it step by step (loading, retrieval, then the auditor's single LLM
  call) and found the LLM call itself was the bottleneck.
- **Change:** A direct API call surfaced the real cause: `openai/gpt-oss-20b` had hit its Groq
  free-tier **daily** token quota (198,165/200,000 used) from the earlier full-184-log B0/B1
  testing. Our retry loop (10 attempts, up to 30s backoff) was retrying a limit that can't clear
  within any backoff window, burning ~3-5 minutes per call for nothing. Confirmed quotas are
  per-model (other models on the same key still had headroom), switched the default model to
  `qwen/qwen3.8-27b`, and made the provider recognize a "tokens per day" error and fail
  immediately instead of retrying. Also added an explicit 30s client timeout as a safety net.
- **Effect:** E3 on 20 real logs (Hand-Crafted + Algorithm-Generated) completed in ~15 minutes:
  **40% agent-level accuracy, 20% step-level, but only 5% verified rate.** Spot-checking
  individual runs shows this isn't a bug: the Verifier sometimes rejects a claim that later
  matches ground truth (e.g. run `e6bc9808...`: `agent_correct=true`, `verified=false`) — it is
  simply stricter than it needs to be on single-citation claims. This is real signal for the
  paper's failure analysis (Verifier calibration is a concrete, honest limitation) rather than
  something to hide. `provider_stats` shows avg latency 16.6s/call on this model — slower than
  gpt-oss-20b was, a real cost/accuracy trade-off worth noting in the efficiency (E6) writeup.
- **Still open:** E5 ablation (`--no-verifier`) queued next on the same 20 logs for a
  like-for-like comparison. Full-184-log E1/E2/E3 runs deferred until later (per team decision,
  prioritizing getting the Phase 2 pipeline built first within the 24h window).

## 2026-11-07 — Armish — E5 ablation result: the Verifier is doing its job

- **Observed:** ran the same 20 real logs with `--no-verifier` for a like-for-like E5 comparison
  (see `results/system_results_noverifier.json`, summarized in `results/gap1_ablation_summary.json`).
- **Result:** with the Verifier on, agent accuracy 40% / step accuracy 20%, but only 5% of claims
  pass verification — of those, **0% are wrong** (unsupported-claim rate 0%, beating Phase 1's own
  H1 target of "under 5%"). With the Verifier off, agent accuracy drops slightly to 35% / step
  accuracy drops sharply to 5%, but the system now calls 80% of its claims "verified" — of those,
  **56% are actually wrong**. The Verifier trades coverage for precision: it correctly flags that
  most single-citation claims aren't solid enough to trust, at the cost of verifying very few
  claims at all (1/19 in this sample).
- **Effect:** this is a clean, honest Gap 1 result for the paper's Results/Ablation sections — the
  core claim ("requiring cited records + a Verifier reduces unsupported claims") holds up on real
  data, with the expected precision/recall trade-off as the limitation to discuss.

## 2026-11-07 — Armish — deadline extended to 11-10; picking up deferred work

- **Context:** supervisor extended the Phase 2 deadline from 11-08 to 11-10. Everything previously
  deferred for time is back in scope: a best-effort full-184-log run (not just n=20) for E1/E2/E3,
  Verifier recalibration, more Gap 3 control predicates, and validating Gap 3 against real (not
  just injected) violations. Also adding OpenRouter as a second free-tier provider so an overnight
  batch can survive Groq's daily quota running out.
- **Added `OpenRouterProvider` + `FallbackProvider`** (`src/agentledger/providers.py`): OpenRouter
  is OpenAI-compatible, called via stdlib `urllib` (no new dependency); its free-model list is
  discovered live from `/models` (pricing.prompt == 0) rather than hardcoded, since free slugs
  rotate over time. `FallbackProvider` wraps a list of providers end-to-end — when Groq's own
  5-model chain raises (fully exhausted), it advances to OpenRouter and retries immediately.
  `get_default_provider()` now returns this wrapper automatically when both `GROQ_API_KEY` and
  `OPENROUTER_API_KEY` are set. Not validated against a live OpenRouter key yet — the HTTP/retry
  logic mirrors `GroqProvider`'s (which *was* validated at length against real traffic), and the
  cross-provider switch itself is unit-tested with fake providers (`tests/test_providers.py`,
  no network). 38/38 tests passing.
- **Recalibrated the Verifier's prompt** (`src/agentledger/agents/verifier.py`): the n=20 failure
  analysis found the Verifier is high-precision/low-recall — all 4 fully-correct predictions in
  that sample were still rejected. Changed the prompt from "do the cited records actually support
  this claim?" to "are the cited records relevant and consistent with this claim" (accepting one
  clearly-relevant citation instead of demanding full corroboration), per that file's own stated
  fix. **Not yet re-measured against live data** — needs a real run to compare verified_rate /
  unsupported_claim_rate against the pre-change numbers in `results/gap1_ablation_summary.json`.
- **Still open:** full-184-log best-effort run (queued for overnight via
  `scripts/run_overnight_full.ps1` + a Windows Scheduled Task, so it survives this session
  restarting); re-measuring the Verifier change; more Gap 3 predicates; Gap 3 validation against
  real violations. Waiting on `GROQ_API_KEY`/`OPENROUTER_API_KEY` to actually run anything live.

## 2026-11-07 (late) — Armish — keys added, overnight task scheduled, one real OpenRouter bug caught

- **Keys set** in `.env` (gitignored): `GROQ_API_KEY`, `OPENROUTER_API_KEY`. Both smoke-tested with
  a single minimal call each before relying on them unattended.
- **Bug found and fixed in `OpenRouterProvider`** (same session, before any real eval traffic):
  the smoke test hit `HTTP 403` on the first discovered free model
  (`liquid/lfm-3-1.7b:free`, routed to an upstream backend OpenRouter's error body labelled
  `"provider_name":"Stealth"`, region-unavailable) and the original code treated *any* non-429
  HTTP error as fatal — raising immediately instead of switching models, which would have killed
  the whole overnight run on the very first region-blocked model. Fixed: a 401 (bad key) still
  raises immediately since no model will work either way, but any other non-429 HTTP error now
  falls through to the same "switch to next free model" path as retry-exhaustion. Re-tested after
  the fix: succeeded on the first call. 41/41 tests still passing (this path isn't covered by the
  offline `FallbackProvider` unit tests, since it needs a real HTTP error from a real model — noted
  as a real gap, not pretending otherwise).
- **Scheduled** a one-time Windows Scheduled Task (`AgentLedgerOvernightFull`, registered via
  PowerShell's `Register-ScheduledTask`, not `schtasks.exe`'s locale-dependent date strings) firing
  at local midnight (2026-11-08T00:00 — confirmed against `Get-Date`, not the Bash tool's own `date`
  output, which reported a different, apparently-wrong timezone than the actual Windows clock task
  scheduler uses). `WakeToRun`, `AllowStartIfOnBatteries`, `DontStopIfGoingOnBatteries`, and a 10h
  execution limit are all set so an overnight run survives sleep/lock/battery. Ran a static
  PowerShell parse-check on `scripts/run_overnight_full.ps1` and independently verified its
  `.env`-parsing block in a fresh process — did not actually execute the real eval scripts tonight,
  to avoid spending any of the day's free-tier quota before the scheduled run gets it.
- **Scope for tonight's run, per team decision:** best-effort against the full 184-log real
  Who&When benchmark for E1 (B0), E2 (B1 `all_at_once`), and E3 (our system) — not capped to a
  fixed N, since each script already skips a failed run and fails fast once a model/provider is
  truly exhausted (see `providers.py`'s "tokens per day" / HTTP-429 fast paths), so "run until
  quota is gone" and "run as many as possible" are the same thing here, not two different asks.
  E3 uses the recalibrated Verifier prompt by default (nothing to separately configure) — so
  tonight's `results/system_results_full184.json` will reflect the new prompt at full scale, but
  is **not** a controlled before/after comparison against the existing n=20 numbers in
  `results/gap1_ablation_summary.json` (that run differs in both sample size and prompt at once).
  A clean, isolated recalibration ablation (same 20 logs, prompt-only difference) is deferred to
  after tonight's run finishes, to avoid competing with it for quota.
- **Still open:** the isolated Verifier-recalibration ablation; more Gap 3 predicates (6/12 now;
  added CTRL-06 earlier tonight); validating Gap 3's predicates against real (non-synthetic)
  violations.

## 2026-11-07 (late) — Armish — Gap 3 real-data validation: found and fixed two real bugs

- **CTRL-03/CTRL-11 have zero real triggers across all 184 real logs** — not a bug, just a fact
  about this benchmark (reasoning/search/code tasks, no `delete`/`pay`-style tool calls or
  password-shaped arguments anywhere in it). These two can only be evaluated on the synthetic
  injected-violation suite; there is no real data to check them against in Who&When at all.
- **CTRL-07 triggers on 145/184 real logs.** Hand-labeled a reproducible sample (`seed(42)`,
  n=16: 8 predicted-pass + 8 predicted-fail) against genuine human judgment, not the predicate's
  own output. Found, before any fix: real precision 83% (5/6), recall 71% (5/7) — not the
  synthetic suite's 1.00. Also found a benign `autogen_magentic_one` framework warning
  (`...Model mapping may be incorrect`) that appears in 58/184 real runs and is the *sole*
  CTRL-07 trigger on 13/184 of them — pure logging noise, not a real failure.
- **Fixed** (`src/agentledger/controls.py`): strip that known warning string before error-keyword
  matching; broadened `_CORRECTIVE_WORDS` to include natural phrasing ("try again", "reformat",
  "redo"); allowed a same-step self-correction (error + fix in one message), not only a strictly
  later one. Re-measured: full-184 distribution shifts from (vacuous 39 / pass 38 / fail 107) to
  (52 / 93 / 39) — the +13 vacuous matches the 13 boilerplate-only-trigger runs exactly. On the
  same 16-case sample: recall improves to 100% (7/7, both real false negatives now caught) at a
  precision cost, 78% (7/9) — the same-step allowance also introduced one new false positive
  (a long planning paragraph that happens to contain "correctly" elsewhere in the same message,
  about a future step, not a real fix). A genuine trade-off, not a strict win — same shape of
  finding as Gap 1's own Verifier precision/recall trade-off. Full write-up:
  `results/gap3_real_violation_validation.md`. Added 3 regression tests
  (`tests/test_controls.py`) for the specific cases this fix targets. 44/44 tests passing.
  Sample size (n=16, n=9 genuine non-ambiguous) is small — treated as illustrative, not a robust
  estimate, same honesty standard as the rest of this project's n=20 numbers.
- **Also fixed in passing:** `eval/run_system.py`'s trajectory filenames were keyed on `run_id`
  alone, but the real Who&When release has 45 `question_ID` collisions across the
  Hand-Crafted/Algorithm-Generated split (confirmed: `Algorithm-Generated/125.json` and
  `Hand-Crafted/1.json` share one) — at full-184 scale this would have silently overwritten ~45
  trajectory files pairwise in tonight's `logs_full184/`. Scoring itself was never affected
  (ground truth is compared per run object, never looked up by run_id) and the existing n=20
  subset has zero collisions, so none of the headline results or existing `logs/` files needed
  fixing — only this filename, now index-prefixed. Caught before tonight's overnight run, not
  after.
- **Remaining:** the isolated Verifier-recalibration ablation (same 20 logs, prompt-only
  before/after) — deferred to after tonight's overnight run so it doesn't compete for quota.

## 2026-11-07 (late) — Armish — extended the injected-violation suite to CTRL-06; fixed a real count bug

- **Extended Gap 3's injected-violation suite** (`eval/make_injected_violations.py`) with 10
  violate + 10 clean CTRL-06 cases (a tool call with no recorded `result` vs. one with a result
  set), and added CTRL-06 to `eval/run_policy_eval.py`'s `_SCORED_CONTROLS`. Re-ran: all 4 scored
  controls (CTRL-03/06/07/11) still score precision=recall=F1=1.00 on their own 20 cases each
  (same honest caveat as before — deterministic rules scored on their own design pattern). The
  other 3 controls' existing cases all correctly contribute true negatives for CTRL-06 (their
  tool calls already had `result` set), confirming the extension didn't disturb anything.
- **Also fixed a real, pre-existing documentation bug while re-counting:** every write-up
  (README, `main.tex`, `results/e5_ablation_gap3.md`) claimed the suite had "30 cases" / "10
  each" for 3 controls — the actual generator produces 10 *violate* + 10 *clean* per control
  (20 per control), so the true original total was 60, not 30; confirmed directly from the
  filesystem (`ls data/injected_violations | wc -l` → 80 now, for 4 controls × 20). Fixed the
  count everywhere it's stated going forward; left the original 2026-11-07 devlog entry above
  as-is since this log is append-only and that entry correctly reflects what was believed true
  at the time it was written.
- 44/44 tests still passing (this change only touches the synthetic-data generator and the
  eval script's scored-control list, not any control predicate's code).

## 2026-11-08 — Areej — Gap 2: provenance graph, tamper harness, aggregator, reviewer report

- Built `src/agentledger/provenance.py`: PROV-style links (attributed_to, derived_from, tool call
  -> input/output digests) stored *inside* each ledger payload so the existing hash chain protects them;
  `ProvenanceGraph.from_ledger` rebuilds the graph (lineage + consistency checks);
  `verify_with_anchor` adds an optional external head-hash/length check.
- Built `eval/run_tamper_test.py` (13 tamper types, 779 cases over 83 clean runs, seed 0, no LLM calls).
  First run, bare chain: 72.8% detection. Findings: (1) `LedgerEntry.index` isn't hashed, so index-only
  edits passed (0/43) — fixed in `ledger.verify()` (now 43/43; pre-fix output kept as
  `results/tamper_results_before_index_fix.json`); (2) truncation of the tail and edit+re-hash attacks are
  invisible to a bare chain by construction — only the external anchor catches them. Final: chain 78.3%,
  chain+graph 81.6%, anchored 100.0%, false alarms 0/83, overhead ~0.06 ms/event (target 10 ms).
- Noted that `eval/run_system.py:_build_ledger` (Armish's) hashes only event_id/agent/tool_calls, not
  content. Left untouched per file ownership; the harness uses the full-event builder. Worth telling
  Armish — one-line switch to `build_provenance_ledger` if he wants content covered in E3.
- Added `src/agentledger/reviewer.py` + `eval/audit_report.py`, `eval/aggregate_results.py`
  (`results/gap_resolution_table.md`), and `tests/test_provenance.py`. 49 passed, 2 skipped.
- Honest caveat: synthetic, author-written tampering on 1–5 event logs; the 100% is anchor-dependent.

## 2026-11-08 (later) — Areej — reran Gap 2 tamper test on the real Who&When data

- The first tamper run (above) used only synthetic logs because the real release wasn't on this
  machine. Cloned `ag2ai/Agents_Failure_Attribution` to a sibling folder (outside the repo) and added
  `--real-whowhen-root` to `eval/run_tamper_test.py`. Real run: 184 logs, 4,092 events, 6,624 tamper
  cases: bare chain 75.0%, chain+graph 82.5%, anchored 100.0%, false alarms 0/184, overhead
  ~0.10 ms/event. Same pattern as synthetic: only the anchor catches truncation and re-hash attacks.
- `edit_tool_result` is N/A on the real release (no tool calls in its history). The aggregator now
  prefers `results/tamper_results_real184.json`; synthetic results kept as a secondary check.
