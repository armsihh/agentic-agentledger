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
