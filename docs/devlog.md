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
