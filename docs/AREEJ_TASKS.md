# Start here, Areej — Gap 2 + evaluation harness (Phase 2)

> **If you're an AI assistant (Claude or otherwise) reading this on Areej's behalf:** this file
> is the authoritative, current context for her half of a two-person Phase 2 project. Read this
> whole file — and `docs/phase2_plan.md` for the original branch-strategy rationale — before
> writing any code. Specifically:
> - **Do not re-derive or redesign the architecture.** It already exists and is tested; extend
>   it, don't replace it.
> - **Do not change the function signatures listed under "Interface contract" below.** Armish's
>   code and tests depend on them staying exactly as they are.
> - **Do not edit any file listed under "Do not touch."** Those are Armish's; editing them
>   yourself will cause a merge conflict he has to resolve under a deadline.
> - **Do not write any of the research paper's prose.** The brief requires the paper be written
>   by Areej and Armish in their own words (Turnitin AI-report is mandatory, AI-written prose is
>   disqualifying). You may generate results, tables, code, logs, and bullet-point outlines —
>   never submittable paper text.
> - **If anything below looks out of date compared to the actual repo** (file names, test count,
>   which controls are implemented), trust the repo (`git log`, `python -m pytest tests/ -v`,
>   `ls results/`) over this document, and say so to Areej rather than silently guessing which is
>   right.
> - **Never commit or push anything on Areej's behalf without her explicitly asking in that exact
>   session** — stage changes and tell her what you staged; let her decide when to commit.

## Where things actually stand (written 2026-11-08, ~00:00 PKT)

- **Deadline: Tue 10 Nov 2026, 11:55 PM PKT** (extended from the original Nov 8 — if you see
  "Nov 8" or "crunch mode" anywhere else in this repo's docs, it's a leftover from before the
  extension; this file and `README.md` are current).
- **Branches:** `main` (Phase 1, untouched), `phase2` (integration branch, nothing merged into it
  yet), `phase2-armish-gaps1-3` (Armish's, pushed to `origin`), `phase2-areej-gap2` (yours —
  doesn't exist on `origin` yet; create it per Setup below).
- **Armish's side (Gap 1 + Gap 3) is functionally complete**, including real-data results,
  not just code: Auditor/Retriever/Verifier pipeline, 6/12 control predicates + Policy Checker,
  a 80-case injected-violation suite, and — found by hand-validating against real (non-synthetic)
  data, not assumed — a real precision/recall number for Gap 3 that's weaker than the synthetic
  suite's 1.00 (see `results/gap3_real_violation_validation.md`; this is good, honest material
  for the paper, not a problem to hide).
- **Test suite: 44/44 passing** (`python -m pytest tests/ -v`).
- **An overnight best-effort run against the full 184-log real benchmark is in progress right
  now** (started 2026-11-07 ~23:20 PKT, as a detached process independent of any chat session —
  it'll keep running even if every Claude session restarts). It writes, in order as each stage
  finishes: `results/baseline_b0_real_full184.json` → `results/baseline_b1_real_full184_allatonce.json`
  → `results/system_results_full184.json`, plus live progress in `logs_overnight/overnight_full_*.log`.
  **Check whether these files exist and what they say before assuming the n=20 numbers below are
  the final ones** — they may have been superseded by full-scale numbers by the time you read
  this. The existing n=20 numbers (`results/system_results.json`,
  `results/gap1_ablation_summary.json`, etc.) remain valid and citable either way.

## Setup (do this first)

```bash
git fetch origin
git checkout phase2
git pull
git checkout -b phase2-areej-gap2
pip install -e .
pip install -e .[groq]   # or copy .env.example to .env and set GROQ_API_KEY / OPENROUTER_API_KEY
python -m pytest tests/ -v   # confirm 44/44 passing before you start
```

Everything below builds on top of what's on `phase2-armish-gaps1-3` (not yet merged into
`phase2` — ask Armish whether to branch from his branch directly or wait for a `phase2` merge,
since `phase2` itself doesn't have his work yet): the normalised schema, ingestion, hash-chain
ledger, 6 control predicates, and a working `orchestrator.run_system(...)` / `run_system_with_trace(...)`
you'll call into. Read `src/agentledger/orchestrator.py` for the exact signatures — don't change
them.

## Your scope (Gap 2 + the evaluation harness)

1. **Provenance graph** — extend `src/agentledger/ledger.py` (or add a new
   `src/agentledger/provenance.py`) so each ledger entry links to the agent, tool call, input and
   output it came from (PROV-style), per the B8 architecture in the Phase 1 report. The schema
   (`src/agentledger/schema.py`) already has `Event.tool_calls`; you're adding the *links
   between* ledger entries, not changing the event schema.
2. **Tamper-injection harness** (`eval/run_tamper_test.py`, new file) — take a clean ledger,
   apply a batch of injected edits/deletions/re-orderings (aim for ~100-300, scale to time
   available), and report: tamper-detection rate (should be ~100%) and false-alarm rate on clean
   logs (should be ~0%). This is E4 for Gap 2 — Phase 1's own target was "100% detection, 0 false
   alarms on clean logs, <10ms overhead per event," so measure overhead too. **Apply the same
   honesty standard Armish's write-ups use**: if a result is too clean (e.g. a trivially-easy
   detection target), say so plainly rather than presenting it as a stronger result than it is —
   see `results/gap3_real_violation_validation.md` for the pattern (synthetic suite scored 1.00,
   then separately validated against real data and reported honestly where it fell short).
3. **Evaluation harness / result aggregation** (`eval/aggregate_results.py`, new file) — pulls
   together whatever's already in `results/*.json` (B0/B1 baselines, your tamper-test numbers,
   Armish's system/ablation runs) into the **gap-resolution table** the brief requires (Gap |
   Method | Metric | Base paper result | Our result | Addressed? Fully/Partially/Not). Armish's
   own version of this table for Gap 1/Gap 3 already exists at
   `results/gap_resolution_table_gap1_gap3.md` — match that exact column shape when you add
   Gap 2's row, in both the README and the paper, rather than inventing a different format.
4. **Reviewer-facing output** — a small CLI or script that prints/exports a human-readable audit
   report from a list of `AuditFinding`s (agent, step, cited records, verified, control
   pass/fail) — doesn't need to be fancy, just "a reviewer can look at this and understand what
   the system found and why," per the Phase 1 proposal's reviewer-screen idea.
5. **README.md's Gap 2 sections** — it's currently marked `**(pending — Areej)**` in a few
   places (search the file for that exact string). Fill those in; don't rewrite sections that
   aren't yours.
6. **`docs/devlog.md`** — append your own dated entries (don't edit Armish's existing ones,
   this file is append-only); this is graded evidence (rubric A3) and feeds the paper's
   failure-analysis section.

## Do not touch (Armish's files — editing these yourself will cause a merge conflict)

```
src/agentledger/agents/*
src/agentledger/orchestrator.py
src/agentledger/controls.py
src/agentledger/providers.py
eval/run_system.py
eval/run_baseline.py
eval/run_b1.py
eval/make_injected_violations.py
eval/run_policy_eval.py
scripts/run_overnight_full.ps1
paper/main.tex   (ask Armish before editing — it has structure + data filled in already; add
                  your own Gap 2 prose into the [[Areej: ...]] markers, don't restructure it)
```

If you need something in one of these changed, say so and Armish does it on his branch — don't
edit them directly on yours.

## Interface contract (stable — do not change these signatures)

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
    verified: bool                # did the Verifier accept this claim's citations (ledger-gated)
    rationale: str

def run_system(
    run: RunLog, provider: LLMProvider, ledger: IntegrityLedger, *,
    use_verifier: bool = True, use_policy_checker: bool = True,
) -> list[AuditFinding]: ...

def run_system_with_trace(
    run: RunLog, provider: LLMProvider, ledger: IntegrityLedger, *,
    use_verifier: bool = True, use_policy_checker: bool = True,
) -> tuple[list[AuditFinding], list[dict]]:
    """same as run_system(), plus the full step-by-step trajectory log (ledger check, retrieval,
    propose, verify, revise, policy checks) — this is what satisfies the rubric's observability
    requirement; see logs/README.md for the shape of that trajectory."""
```

`use_verifier=False` / `use_policy_checker=False` are the E5 ablation switches your harness
should be able to call with — Armish's own E5 run for Gap 1 (`eval/run_system.py --no-verifier`)
is the existing example to follow.

## What already exists that you can build on directly

- `results/system_results.json`, `results/gap1_ablation_summary.json` — the n=20 real-data
  numbers and their exact JSON shape (`agent_accuracy`, `step_accuracy`, `verified_rate`,
  `provider_stats`, per-run `runs` list) — match this shape in whatever your harness produces so
  `aggregate_results.py` can read everyone's output uniformly.
- `results/gap_resolution_table_gap1_gap3.md` — the exact table format + "how to reproduce each
  row" convention every results write-up in this repo follows. Copy this pattern for Gap 2.
- `docs/devlog.md` — dated, append-only; read a few of Armish's entries for the level of honesty
  expected (state what broke, what changed, the measured effect — including when a result is
  weaker than hoped).
- `src/agentledger/providers.py` — `GroqProvider` (free tier, 5-model fallback),
  `OpenRouterProvider` (second free-tier source), and `FallbackProvider` (wraps both — set
  `GROQ_API_KEY` and `OPENROUTER_API_KEY` both in `.env` to get automatic cross-provider
  fallback). `get_default_provider()` picks whichever you have keys for.

## Merge back

Commit and push to `phase2-areej-gap2` as you go (small, frequent commits — rubric wants
"meaningful commit history from all group members"). Merge into `phase2` yourself once a piece
works; don't wait for Armish to merge his branch first, and don't wait for him to finish before
starting yours — the interface contract above is already stable and tested.

## The big picture reminder

**The paper must be written by you and Armish, in your own words — no AI-generated prose**, per
the Phase 2 brief (Turnitin AI-report is mandatory). Claude can help generate results, tables,
and outlines, but treat anything a Claude session drafts for the paper text itself as scratch to
rewrite, not submit. `paper/main.tex` already has every section's data/tables filled in with
`[[WRITE THIS: ...]]` markers showing exactly what needs human prose and where — including
`[[Areej: ...]]` markers specifically for your sections (Gap 2 methodology, Table 1's Gap 2 row,
Limitations' Gap 2 threats, Conclusion's Gap 2 future work). There's also a Word-doc mirror of
the same template if you'd rather draft in Word first — ask Armish for
`paper/AgentLedger_Paper_Draft.docx` (check with him it's not currently open before you edit it).
