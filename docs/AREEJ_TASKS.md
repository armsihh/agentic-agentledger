# Areej's part — Phase 2 (crunch mode, deadline Sun 8 Nov 2026 11:55 PM PKT)

Hi Areej — this is your half of Phase 2, written so you (or your own Claude session) can start
immediately without waiting on Armish. Read `docs/phase2_plan.md` first for the full context
(branch strategy, timeline, why things are split this way); this file is just your task list.

## Setup (do this first)

```bash
git fetch origin
git checkout phase2
git pull
git checkout -b phase2-areej-gap2
```

Everything below builds on top of what's already on `phase2`: the normalised schema, ingestion,
hash-chain ledger, 5 control predicates, and a working `orchestrator.run_system(...)` you'll call
into. Read `src/agentledger/orchestrator.py` for the exact function signature — don't change it,
Armish's code and your harness both depend on it staying stable.

## Your scope (Gap 2 + the evaluation harness)

1. **Provenance graph** — extend `src/agentledger/ledger.py` (or add
   `src/agentledger/provenance.py`) so each ledger entry links to the agent, tool call, input and
   output it came from (PROV-style), per the B8 architecture in the Phase 1 report. The schema
   (`src/agentledger/schema.py`) already has `Event.tool_calls`; you're adding the *links between*
   ledger entries, not changing the event schema.
2. **Tamper-injection harness (`eval/run_tamper_test.py`, new file)** — take a clean ledger, apply
   a batch of injected edits/deletions/re-orderings (aim for ~100-300, scale to time available),
   and report: tamper-detection rate (should be ~100%) and false-alarm rate on clean logs (should
   be ~0%). This is E4 for Gap 2 — the Phase 1 proposal's own target was "100% detection, 0 false
   alarms on clean logs, <10ms overhead per event," so measure overhead too.
3. **Evaluation harness (`eval/aggregate_results.py`, new file)** — pulls together whatever's
   already in `results/*.json` (B0/B1 baselines, your tamper-test numbers, Armish's system/ablation
   runs) into the **gap-resolution table** the Phase 2 brief requires (Gap | Method | Metric |
   Base paper result | Our result | Addressed? Fully/Partially/Not). This table must appear in
   both the README and the paper, so get the shape right early — ask Armish for his `results/`
   file names/schemas rather than guessing.
4. **Reviewer-facing output** — a small CLI or script that prints/exports a human-readable audit
   report from a list of `AuditFinding`s (agent, step, cited records, verified, control pass/fail)
   — doesn't need to be fancy, just "a reviewer can look at this and understand what the system
   found and why," per the Phase 1 proposal's reviewer-screen idea.
5. **README.md** — project overview, architecture diagram (can reuse/adapt
   `doc/figure1_architecture.png` from Phase 1), install steps, env vars (`GROQ_API_KEY` is the
   one we're actually using — free tier, see `src/agentledger/providers.py`), how to run each
   experiment E1–E6, and the gap-resolution table.
6. **`docs/devlog.md`** — append your own dated entries (don't edit Armish's); this is graded
   evidence (rubric A3) and feeds the paper's failure-analysis section.

## What NOT to touch (Armish's files, to avoid merge conflicts)

`src/agentledger/agents/*`, `src/agentledger/orchestrator.py`, `src/agentledger/controls.py`,
`eval/run_system.py`, `eval/make_injected_violations.py`, `eval/run_policy_eval.py`. If you need
something from these changed, say so and he'll do it on his branch — don't edit them directly on
yours, merge conflicts will cost us time we don't have.

## Merge back

Commit and push to `phase2-areej-gap2` as you go (small, frequent commits — rubric wants
"meaningful commit history from all group members"). Merge into `phase2` yourself once a piece
works; don't wait for Armish to merge for you, and don't wait for him to finish his piece before
starting yours — the interface contract in `orchestrator.py` is already stable.

## The big picture reminder

**The paper must be written by you and Armish, in your own words — no AI-generated prose**, per
the Phase 2 brief (Turnitin AI-writing report is mandatory). Claude can help generate results,
tables, and outlines, but treat anything a Claude session drafts for the paper text itself as
scratch to rewrite, not submit.
