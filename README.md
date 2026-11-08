# AgentLedger

Evidence-bound, tamper-evident, control-mapped auditing of agent logs. AI4015
project **G1-04**: *From Agent Logs to Audit Evidence: Compliance-Grade
Traceability for Agentic AI*.

> **Status:** Phase 2, in progress (deadline extended to 2026-11-10). This
> README is a working draft — Gap 2 (provenance graph, tamper-detection
> harness, reviewer UI) is Areej's piece and not folded in here yet; see
> `docs/AREEJ_TASKS.md` and `docs/phase2_plan.md` for the plan. Sections below
> marked **(pending)** are hers to complete.

See `doc/Agentic Phase 1 (fixed).docx` for the full literature review, research
gaps, and project proposal this code implements, and
`doc/figure2_phase2_status.png` for the current architecture / implementation
status diagram.

## Changes since Phase 1

- Added a free-tier `GroqProvider` (`src/agentledger/providers.py`) with
  automatic model fallback (Groq's free tier caps each model at ~200k
  tokens/day; the provider falls through a chain of models instead of
  failing when one is exhausted) — see `docs/devlog.md` for how this was
  diagnosed and fixed.
- Built the Gap 1 agentic pipeline: `src/agentledger/agents/{retriever,
  auditor, verifier}.py`, tied together by `src/agentledger/orchestrator.py`.
- Extended the Gap 3 control catalogue from 2 to 6 implemented predicates
  and added a Policy Checker (`src/agentledger/agents/policy_checker.py`)
  plus a 30-case injected-violation suite (`eval/make_injected_violations.py`,
  `eval/run_policy_eval.py`).
- Re-ran B0/B1 baselines on the **real** Who&When benchmark (not just the
  3-log synthetic sample) for a fair comparison against the new system.

## Gap-resolution table

Full write-up, reproduction commands, and honest caveats in
[`results/gap_resolution_table_gap1_gap3.md`](results/gap_resolution_table_gap1_gap3.md).
Summary (20-log real Who&When subset; **not yet the full 184-log benchmark**
— see `docs/devlog.md`):

| Gap | Method / component | Metric | Base paper (E2) | Ours (E3) | Addressed? |
|---|---|---|---|---|---|
| Gap 1 | Auditor + Retriever + Verifier | agent / step accuracy | 40.0% / 25.0% | 40.0% / 20.0% | Partially — accuracy is on par, not a clear win at this sample size |
| Gap 1 | — same — | **unsupported-claim rate** (the real target metric) | n/a (no citation mechanism exists to compare) | **0.0%** (vs. 56.3% with the Verifier removed — see `results/gap1_ablation_summary.json`) | **Fully** — beats Phase 1's H1 target of <5% |
| Gap 2 done by areej | Integrity Ledger + provenance graph + tamper harness | detection / false-alarm rate / overhead | n/a (base paper has no integrity mechanism) | **100% / 0% / ~0.1 ms per event** on all 184 real Who&When logs (6,624 injected tampers) — but only **75.0%** without an external anchor; truncation and full re-hash need it. See [`results/gap2_tamper_validation.md`](results/gap2_tamper_validation.md) | **Fully** for injected tampering of real logs, with that anchor caveat |
| Gap 3 | Policy Checker, 6/12 predicates | precision / recall / F1 | n/a | 1.00 / 1.00 / 1.00 on the injected-violation suite (honest caveat: deterministic rules scored on their own design patterns — see `results/e5_ablation_gap3.md`) | **Fully** (for the 4 predicates the injected-violation suite scores — CTRL-03/06/07/11; the other 2 implemented predicates have no planted ground truth to score against yet) |

## What's here

- **Normalised schema** (`src/agentledger/schema.py`) — the `RunLog`/`Event`
  state/context structure every log format is ingested into.
- **Ingestion** (`src/agentledger/ingestion.py`) — Who&When-style JSON
  (synthetic and the real release, both Hand-Crafted and Algorithm-Generated
  subsets, via `load_whowhen_release_full`).
- **Integrity Ledger** (`src/agentledger/ledger.py`) — SHA-256 hash chain for
  Gap 2. Provenance graph (`src/agentledger/provenance.py`, PROV-style
  links between each entry and its agent / tool call / input / output, stored inside the hashed
  payload) plus `verify_with_anchor()` for truncation and re-hash attacks.
- **Control catalogue** (`src/agentledger/controls.py`) — 12 declared
  controls mapped to ISO/IEC 42001 clauses and NIST AI RMF functions; **6
  implemented** (CTRL-01, 02, 03, 06, 07, 11), 6 remain declared-but-unbuilt
  (each with a stated reason in code — mostly org-level evidence a single
  run's log structurally can't contain, e.g. a risk treatment plan) and are
  skipped (not silently passed) by the Policy Checker.
- **Gap 1 agents** (`src/agentledger/agents/{retriever,auditor,verifier}.py`)
  — a Retriever that shortlists candidate records instead of reading the
  whole log, an Auditor that proposes an agent/step claim citing specific
  record ids, and a Verifier that re-reads only those records and rejects
  unsupported claims (one revision pass).
- **Gap 3 agent** (`src/agentledger/agents/policy_checker.py`) — runs every
  implemented control predicate over a ledgered trajectory.
- **Orchestrator** (`src/agentledger/orchestrator.py`) — `run_system(...)`,
  the single entry point tying Auditor → Verifier → Policy Checker together,
  gated by the ledger's integrity check; `use_verifier` / `use_policy_checker`
  flags are the ablation switches for E5.
- **Model provider interface** (`src/agentledger/providers.py`) — Mock
  (offline, deterministic), Groq (free tier, with model fallback — what the
  real-data runs below actually use), or Anthropic (paid, if you have a key).
- **Baselines B0/B1** (`src/agentledger/baselines/`) — B0 from scratch; B1
  re-implements the base paper's own three attribution methods, adapted from
  its public code (kept as a separate reference clone, see below).
- **Injected-violation suite** (`data/injected_violations/`, generated by
  `eval/make_injected_violations.py`) — 80 synthetic cases (20 each for
  CTRL-03/06/07/11, clean + violating) with planted ground truth.
- **Reviewer-facing output** (`src/agentledger/reviewer.py`, `eval/audit_report.py`) — prints a
  per-run audit report: ledger integrity, attribution with cited records and verified flag, and
  control pass/fail.
- **Tamper harness** (`eval/run_tamper_test.py`) and **result aggregator**
  (`eval/aggregate_results.py` → `results/gap_resolution_table.md`).
- **Test suite** (`tests/`) — 38 tests: ingestion, ledger, baselines, all 5
  implemented controls, and the full Gap 1 agent pipeline (retriever,
  auditor, verifier, orchestrator, ablation flags, trajectory logging).

## Reference repo (base paper's code — kept separate)

The base paper's own implementation,
[`ag2ai/Agents_Failure_Attribution`](https://github.com/ag2ai/Agents_Failure_Attribution)
(MIT licensed), is cloned **outside this repo**, as a sibling folder:

```
agentic/
  project/                               <- this repo
  reference-Agents_Failure_Attribution/  <- read-only clone, not part of this repo
```

Clone it yourself one level up if you don't have it:

```bash
git clone https://github.com/ag2ai/Agents_Failure_Attribution.git ../reference-Agents_Failure_Attribution
```

It has the real Who&When benchmark at `../reference-Agents_Failure_Attribution/Who&When/{Hand-Crafted,Algorithm-Generated}/`.

## Application interface

Every experiment (E1–E6) is run through an argparse CLI in `eval/*.py` (each takes `--help`).
This is the "reproducible execution workflow" option the brief allows as an alternative to a
GUI/web app — see "Running it" below for the exact commands.

## Setup

```bash
pip install -e .
pip install pytest   # or: pip install -e .[dev]
```

Copy `.env.example` to `.env` and fill in a provider key (free Groq is what
every real-data result in `results/` actually used):

```bash
cp .env.example .env
# then set GROQ_API_KEY (free, get one at https://console.groq.com)
pip install -e .[groq]
export GROQ_API_KEY=gsk_...   # Windows: set GROQ_API_KEY=gsk_...
```

Optionally also set `OPENROUTER_API_KEY` (free, get one at
https://openrouter.ai/keys). With both set, `get_default_provider()` wraps
them in a `FallbackProvider` (`src/agentledger/providers.py`): when Groq's
free-tier daily quota is exhausted across all 5 of its own fallback models,
the run falls through to OpenRouter's free models automatically instead of
failing, mid-run, with no manual intervention — the same reliability
mechanism as Groq's own model-fallback chain, one level up.

With no key set, everything runs against the deterministic, offline
`MockProvider` instead — useful for the test suite, not representative of
real accuracy.

## Running it

> **Note on repo layout vs. the Phase 2 brief's suggested structure:** the brief suggests an
> `experiments/` folder for E1–E6 configs/scripts; this repo keeps that in `eval/` instead, since
> that's where Phase 1's baseline workflows already lived and every E1–E6 script below is just an
> extension of the same pattern. Functionally equivalent — scripts here, results in `results/`,
> same as the brief asks for. Agent traces/observability output lives in `logs/` as suggested
> (see `eval/run_system.py --trajectory-dir`, default `logs`).

```bash
# test suite
python -m pytest tests/ -v

# E1 — baseline B0 on the real Who&When subset
python eval/run_baseline.py --real-whowhen-root "../reference-Agents_Failure_Attribution/Who&When" --limit 20

# E2 — baseline B1 (base paper method), same subset
python eval/run_b1.py --real-whowhen-root "../reference-Agents_Failure_Attribution/Who&When" --limit 20 --method all_at_once

# E3 — the full system
python eval/run_system.py --real-whowhen-root "../reference-Agents_Failure_Attribution/Who&When" --limit 20

# E5 — ablation: remove the Verifier
python eval/run_system.py --real-whowhen-root "../reference-Agents_Failure_Attribution/Who&When" --limit 20 --no-verifier

# E4/Gap 3 — injected-violation suite
python eval/make_injected_violations.py
python eval/run_policy_eval.py

# E4/Gap 2 — tamper-injection harness (no LLM calls), reviewer report, table aggregation
python eval/run_tamper_test.py --real-whowhen-root "../reference-Agents_Failure_Attribution/Who&When" --reps 3 --out results/tamper_results_real184.json
python eval/audit_report.py --from-results results/system_results.json --index 0
python eval/aggregate_results.py
```

Every script prints a live accuracy summary and writes full per-run results
to a file under `results/`. `--limit N` controls the sample size; omit it to
run the full 184-log benchmark (slow on the free tier — budget hours, not
minutes; see `docs/devlog.md`).

## Results & write-ups

- [`results/gap_resolution_table_gap1_gap3.md`](results/gap_resolution_table_gap1_gap3.md) — the assembled gap-resolution table, reproduction commands, honest summary.
- [`results/failure_analysis_gap1.md`](results/failure_analysis_gap1.md) — failure categories, frequencies, representative success/failure cases with trajectories.
- [`results/gap2_tamper_validation.md`](results/gap2_tamper_validation.md) — Gap 2 tamper-test results, per-mode detection, honest caveats.
- [`results/e5_ablation_gap3.md`](results/e5_ablation_gap3.md) — why/how Gap 3's ablation is measured via the injected-violation suite.
- [`results/e6_efficiency.md`](results/e6_efficiency.md) — cost/latency/reliability comparison across E1/E2/E3/E5.
- [`results/gap1_ablation_summary.json`](results/gap1_ablation_summary.json) — the computed grounded-correct / unsupported-claim metrics.
- `docs/devlog.md` — dated development log (what broke, what changed, measured effect).

## Data

`data/sample_logs/` — three small synthetic logs for fast smoke tests.
`data/injected_violations/` — the Gap 3 ground-truth suite. Real data comes
from the reference repo (see above); point any `eval/*.py` script's
`--real-whowhen-root` at it.

## Layout

```
src/agentledger/
  schema.py                    normalised Event/RunLog model
  ingestion.py                 log-format -> RunLog (synthetic + real Who&When release)
  ledger.py                    hash-chain Integrity Ledger
  provenance.py                 PROV-style provenance graph + anchored verification (Gap 2)
  reviewer.py                   human-readable audit report
  controls.py                  ISO/IEC 42001 + NIST AI RMF control catalogue (6/12 implemented)
  tools.py                      read_span / search_log / get_provenance / verify_chain / check_control
  providers.py                  LLM provider interface (mock / Groq with fallback / Anthropic)
  orchestrator.py               run_system(): Auditor -> Verifier -> Policy Checker, ledger-gated
  agents/
    retriever.py                 candidate-record shortlisting (Gap 1)
    auditor.py                   cited-claim proposal (Gap 1)
    verifier.py                  citation re-check + reject/revise (Gap 1)
    policy_checker.py            runs implemented control predicates (Gap 3)
  baselines/
    b0_single_call.py            baseline B0 (from scratch)
    b1_whowhen_reference.py      baseline B1 (adapted from the reference repo)
data/
  sample_logs/                 synthetic smoke-test logs
  injected_violations/         Gap 3 ground-truth suite (generated)
eval/
  run_baseline.py               E1 workflow (B0)
  run_b1.py                     E2 workflow (B1)
  run_system.py                 E3/E5 workflow (full system + ablation flags)
  run_tamper_test.py            E4 Gap 2 tamper-injection harness
  aggregate_results.py          builds the gap-resolution table from results/*.json
  audit_report.py               reviewer-facing report CLI
  make_injected_violations.py   generates the Gap 3 suite
  run_policy_eval.py            E4 workflow for Gap 3
results/                       all experiment outputs + write-ups (see above)
logs/                          per-run agent trajectories (reasoning steps, tool calls,
                                revisions, policy checks) for reported E3/E5 runs -- see
                                `eval/run_system.py --trajectory-dir`
tests/                         pytest suite (38 tests)
docs/
  phase2_plan.md                branch strategy, file ownership, interface contract
  AREEJ_TASKS.md                 Areej's task list
  devlog.md                      dated development log
doc/                            Phase 1 literature review, gaps & proposal (.docx), architecture diagrams

../reference-Agents_Failure_Attribution/   base paper's own code (sibling folder, not part of this repo)
```
