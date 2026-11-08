# Phase 2 game plan (deadline extended to Tue 10 Nov 2026, 11:55 PM PKT)

> **Superseded for current task/file-ownership details:** this plan was written 2026-11-07 for
> the original ~24h window and the file-ownership table below no longer matches reality (e.g. it
> assigns `eval/run_system.py` to Areej; Armish built it). Read this for the *rationale* behind
> the branch split and the interface contract (still accurate), but for Areej's current task
> list, current file ownership, and current repo state, **use `docs/AREEJ_TASKS.md` instead** —
> it's kept up to date and is the authoritative one.

Written 2026-11-07 with ~24h left. This is the shared contract between Armish's and Areej's
work so both can build in parallel on the same repo without blocking each other or colliding
on files. Read this before touching code.

## Hard constraints from the Phase 2 brief

- **AI must not write the paper.** Claude (either of our sessions) may generate results, tables,
  code, logs, and bullet-point outlines, but the submitted paper prose must be written by Armish
  and Areej in their own words — Turnitin's AI-writing report is mandatory and the brief says
  AI-generated writing is disqualifying. Treat anything Claude drafts for the paper as a
  throwaway outline/data dump to rewrite, not submittable text.
- Every number in the paper must come from a file in `results/` reproducible by a script in
  `experiments/` or `eval/`. No hand-typed numbers.
- Test set is not for tuning. Any prompt/threshold iteration happens on a small dev slice we
  carve out of the sample logs or a held-out few real Who&When cases, never on the full real set
  we report on.

## Triage: what we are actually building in ~20 hours

Given the timeline, we are **not** attempting all three gaps at full depth. Priorities:

1. **Gap 1 (evidence-bound findings) — flagship, gets the most time.** Auditor + Retriever +
   Verifier loop, citing log record IDs, rejecting unsupported claims. This is what makes the
   system "genuinely agentic" for rubric A1/A2.
2. **Gap 2 (tamper-evident ledger) — mostly already built in Phase 1** (`ledger.py`). Needs: a
   tamper-injection test harness (edits/deletions/re-orderings) and wiring the ledger-verify step
   into the Auditor's loop so it's a real gate, not a side calculation.
3. **Gap 3 (control-level compliance) — thinnest slice.** Extend the control catalogue past the
   2 implemented predicates to a handful more, build a minimal Policy Checker that runs predicates
   over a ledgered trajectory, and a small (even if modest, e.g. 20–30 run) injected-violation set.
   Honest, small-scale reporting here is fine — the brief explicitly rewards honest partial
   results over inflated ones.

E1 (baseline/B0) and E2 (base paper/B1) are **already running** against the real Who&When set via
Groq (`results/baseline_b0_real_whowhen.json`, `results/baseline_b1_real_whowhen.json`) — this
doubles as the Phase 1 feedback fix *and* Phase 2's E1/E2. E3 is the new system on the same real
set (or a subset if Groq free-tier throughput forces it — say so plainly if it does). E4 is one
experiment per gap. E5 is ablations (flags to turn Verifier / ledger-check / Policy Checker off).
E6 is call counts / latency, which the provider wrapper should log as it goes.

## Branch strategy

- `main` — Phase 1, untouched except via PR-style merge at the very end.
- `phase2` — integration branch. Both feature branches merge here. This is what becomes the
  `phase2-final` tag.
- `phase2-armish-gaps1-3` — Armish: Auditor/Retriever/Verifier (Gap 1), control catalogue
  extension + Policy Checker (Gap 3), orchestrator, injected-violation suite, E3/E4(Gap1)/E4(Gap3)
  experiments, ablations for these components.
- `phase2-areej-gap2` — Areej: provenance-graph completion on top of the ledger, tamper-injection
  harness + E4(Gap2) experiment, the E1/E2/E5/E6 evaluation harness that aggregates everyone's
  results into `results/` tables, reviewer-facing output, README/docs.

Merge frequently (every working hour, not at the end) into `phase2` so conflicts stay small.
Whoever finishes a vertical slice merges it; don't wait for the other person.

## File ownership (to avoid merge conflicts)

| Area | Owner | Files |
|---|---|---|
| Auditor/Retriever/Verifier agents | Armish | `src/agentledger/agents/auditor.py`, `retriever.py`, `verifier.py` (new) |
| Orchestrator (ties the loop together) | Armish | `src/agentledger/orchestrator.py` (new) |
| Control catalogue + Policy Checker | Armish | `src/agentledger/controls.py` (extends existing), `src/agentledger/agents/policy_checker.py` (new) |
| Injected-violation suite | Armish | `data/injected_violations/`, `eval/make_injected_violations.py` (new) |
| Provenance graph | Areej | `src/agentledger/ledger.py` (extends existing), `src/agentledger/provenance.py` (new, if needed) |
| Tamper-injection harness | Areej | `eval/run_tamper_test.py` (new) |
| Evaluation harness / result aggregation | Areej | `eval/run_system.py` (new, calls Armish's orchestrator — see interface below), `eval/aggregate_results.py` (new) |
| Reviewer interface | Areej | `src/agentledger/reviewer.py` or a small CLI/`streamlit` app (new) |
| README / devlog / docs | Areej (primary), both contribute | `README.md`, `docs/devlog.md` |
| Existing Phase 1 files (schema, ingestion, providers, baselines, tools) | Shared, already stable | don't rewrite wholesale — only extend |

If you need to touch a file outside your area, say so in the PR/merge and keep the diff small.

## Interface contract (so the two halves plug together without a long back-and-forth)

Areej's evaluation harness needs one stable entry point into Armish's system. Armish commits to
this signature early (within the first couple hours) and keeps it stable:

```python
# src/agentledger/orchestrator.py
@dataclass
class AuditFinding:
    run_id: str
    agent: str
    step: int
    control_id: str | None       # None for the plain Gap-1 attribution finding
    passed: bool | None          # None when not a control check
    cited_record_ids: list[str]
    verified: bool               # did the Verifier accept this claim's citations
    rationale: str

def run_system(
    run: RunLog,
    provider: LLMProvider,
    ledger: IntegrityLedger,
    *,
    use_verifier: bool = True,
    use_policy_checker: bool = True,
) -> list[AuditFinding]:
    """End-to-end: Auditor (+Retriever) finds the responsible agent/step with citations,
    Verifier checks citations when use_verifier, Policy Checker runs controls over the
    ledgered trajectory when use_policy_checker. The use_* flags are the ablation switches
    for E5 — Areej's harness calls this with different flag combinations."""
```

Areej's `eval/run_system.py` calls `run_system(...)` per run and writes
`results/system_results.json` with the same `agent_accuracy` / `step_accuracy` shape the
existing `run_baseline.py` / `run_b1.py` already use, plus the new control-level metrics, so the
gap-resolution table can pull from one consistent place.

## Devlog

Append dated entries to `docs/devlog.md` as you go (don't rewrite others' entries) — this is
graded evidence for A3 (iterative improvement) and feeds the paper's failure-analysis section.

## Timeline (rough, ~20h left)

- Hour 0–1: branches + this plan pushed; both start building against the interface above.
- Hour 1–8: Armish builds Auditor/Retriever/Verifier + Policy Checker; Areej builds
  tamper-harness + provenance graph + evaluation harness skeleton (can stub against the
  interface before Armish's real implementation lands).
- Hour 8–12: merge into `phase2`; run E3/E4/E5 for real; fix what breaks.
- Hour 12–16: E6, failure analysis, gap-resolution table filled from `results/`.
- Hour 16–22: paper writing (Armish & Areej, own words) from the frozen `results/` tables;
  README finalized; repo cleanup; `phase2-final` tag.
- Last hours: Turnitin reports, final submission.
