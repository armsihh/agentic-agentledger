# AgentLedger

Evidence-bound, tamper-evident, control-mapped auditing of agent logs. Phase 1
technical foundation for the AI4015 project **G1-04**: *From Agent Logs to
Audit Evidence: Compliance-Grade Traceability for Agentic AI*.

See `doc/Agentic Phase 1 (fixed).docx` for the full literature review, research
gaps, and project proposal this code implements.

## What's here (Phase 1 scope)

This is the **initial technical foundation**, not the full system described in
the proposal's B8 architecture. It covers:

- **Normalised schema** (`src/agentledger/schema.py`) - the `RunLog`/`Event`
  state/context structure every log format is ingested into.
- **Ingestion** (`src/agentledger/ingestion.py`) - one format implemented
  (Who&When-style JSON); TRAIL and MAST-Data follow the same pattern.
- **Integrity Ledger** (`src/agentledger/ledger.py`) - the SHA-256 hash-chain
  for Gap 2. Detects tampering, deletion, and re-ordering of past entries.
- **Control catalogue** (`src/agentledger/controls.py`) - the ~12-control
  catalogue for Gap 3, mapped to ISO/IEC 42001 clauses and NIST AI RMF
  functions. Two predicates (CTRL-01, CTRL-02) are fully implemented; the rest
  are declared with their source/clause and raise `NotImplementedError` until
  the Policy Checker agent is built in Phase 2.
- **Tool interfaces** (`src/agentledger/tools.py`) - `read_span`,
  `search_log`, `get_provenance`, `verify_chain`, `check_control`, called
  directly here; wiring them up as agent-callable tools for the
  Auditor/Verifier/Policy Checker agents is Phase 2 work.
- **Model provider interface** (`src/agentledger/providers.py`) - swappable
  hosted (Anthropic) vs. local model behind one interface, plus an offline
  `MockProvider` so the pipeline runs with no API key.
- **Baseline B0** (`src/agentledger/baselines/b0_single_call.py`) - the
  weakest baseline from B10: one prompt, the whole log, a bare verdict.
  Written from scratch; not derived from any other repo.
- **Baseline B1** (`src/agentledger/baselines/b1_whowhen_reference.py`) - the
  base paper's own three attribution methods (`all_at_once`, `step_by_step`,
  `binary_search`), re-implemented against our schema and provider interface.
  See "Reference repo" below for exactly what was reused and how.
- **Two end-to-end workflows** (`eval/run_baseline.py` for B0, `eval/run_b1.py`
  for B1) - ingest -> ledger -> baseline -> control check -> accuracy + results
  file. `run_b1.py` runs against either the synthetic sample logs or the real
  Who&When benchmark (see "Reference repo").
- **Test suite** (`tests/`) - 18 tests: ingestion, the ledger (including
  tamper detection), B0, B1 (all three methods), the two implemented controls,
  and a real-data smoke test that is skipped automatically if the reference
  repo below isn't present.

Not yet built: the Auditor/Retriever/Verifier/Policy Checker agents, baseline
B2, the reviewer UI, and the full evaluation harness from B12 (including the
compliance-question rubric test). Those are Phase 2.

## Reference repo (base paper's code - kept separate)

The base paper's own implementation,
[`ag2ai/Agents_Failure_Attribution`](https://github.com/ag2ai/Agents_Failure_Attribution)
(MIT licensed), is cloned **outside this repo**, as a sibling folder:

```
agentic/
  project/                            <- this repo
  reference-Agents_Failure_Attribution/  <- read-only clone, not part of this repo
```

Clone it yourself with `git clone https://github.com/ag2ai/Agents_Failure_Attribution.git`
one level up from this project if you don't have it. It is **not** committed
here and has no dependency relationship with this package - it's kept around
purely as a reference for structure/format, per the assignment's expectation
that Deliverable B/C baselines include "the base paper's approach where
applicable."

**What was adapted from it, and where:**
- `src/agentledger/baselines/b1_whowhen_reference.py` mirrors the three
  methods in the reference repo's `Automated_FA/Lib/utils.py`
  (`all_at_once`, `step_by_step`, `binary_search`) - same prompts and control
  flow, each function's docstring says so.
- `src/agentledger/ingestion.py::load_whowhen_release_record` mirrors the
  reference repo's own field convention for the real dataset (`index_agent =
  "role" if is_handcrafted else "name"`, from the same `Lib/utils.py`), so our
  ingestion reads the *actual* Hand-Crafted/Algorithm-Generated JSON files
  byte-for-byte the way their own code does.
- Everything else (`schema.py`, `ledger.py`, `controls.py`, `tools.py`,
  `providers.py`, baseline B0) was written from scratch for AgentLedger and
  has no counterpart in the reference repo.

**Model availability (per the assignment's note to flag unavailable
models):** the reference repo's `inference.py` only supports Azure OpenAI
(`gpt-4o`/`gpt-4`/`gpt-4o-mini`, via `AzureOpenAI`, requiring an Azure
endpoint + key - not a plain OpenAI key) or local Llama-3.1 (8B/70B) /
Qwen2.5 (7B/72B) through `transformers`, needing a GPU with enough VRAM to
hold an 8B+ model. **None of these are available in this environment** - no
Azure OpenAI subscription, no local GPU. `b1_whowhen_reference.py` therefore
runs the same three methods through AgentLedger's own provider interface
instead: `MockProvider` (deterministic, offline) by default, or our
`AnthropicProvider` (Claude, hosted) if you set `ANTHROPIC_API_KEY`. This
substitutes the *model* only - the method logic and prompts are unchanged
from the reference implementation.

## Setup

```bash
pip install -e .
pip install pytest   # or: pip install -e .[dev]
```

To use the real hosted model instead of the offline mock:

```bash
pip install -e .[hosted]
export ANTHROPIC_API_KEY=sk-...   # Windows: set ANTHROPIC_API_KEY=sk-...
```

With no API key set, everything below runs against the deterministic
`MockProvider` - no network access required.

## Running it

```bash
# run the test suite
python -m pytest tests/ -v

# baseline B0, on the synthetic sample logs
python eval/run_baseline.py

# baseline B1, all three methods, on the synthetic sample logs
python eval/run_b1.py

# baseline B1, one method, on a slice of the REAL Who&When benchmark
# (requires the reference repo cloned as described above)
python eval/run_b1.py --method all_at_once \
  --real-whowhen-dir "../reference-Agents_Failure_Attribution/Who&When/Hand-Crafted" \
  --is-handcrafted --limit 20
```

Both scripts print per-run predictions and accuracy, and write full results to
`results/baseline_b0_results.json` / `results/baseline_b1_results.json`.

## Data

`data/sample_logs/` holds three small **synthetic** logs used for the smoke
tests above - see `data/sample_logs/README.md`. For real data, point
`eval/run_b1.py` at the reference repo's benchmark folder, as shown above.

## Layout

```
src/agentledger/
  schema.py            normalised Event/RunLog model
  ingestion.py         log-format -> RunLog (synthetic + real Who&When release)
  ledger.py            hash-chain Integrity Ledger
  controls.py          ISO/IEC 42001 + NIST AI RMF control catalogue
  tools.py              read_span / search_log / get_provenance / verify_chain / check_control
  providers.py          LLM provider interface (mock / hosted)
  baselines/
    b0_single_call.py          baseline B0 (from scratch)
    b1_whowhen_reference.py    baseline B1 (adapted from the reference repo)
data/sample_logs/      synthetic smoke-test logs
eval/run_baseline.py   end-to-end workflow, B0
eval/run_b1.py         end-to-end workflow, B1 (sample or real data)
tests/                 pytest suite (18 tests)
doc/                   Phase 1 literature review, gaps & proposal (.docx)

../reference-Agents_Failure_Attribution/   base paper's own code (sibling folder, not part of this repo)
```
