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
- **One end-to-end workflow** (`eval/run_baseline.py`) - ingest -> ledger ->
  B0 -> control check -> accuracy + results file.
- **Initial test suite** (`tests/`) - 12 tests covering ingestion, the ledger
  (including tamper detection), B0, and the two implemented controls.

Not yet built: the Auditor/Retriever/Verifier/Policy Checker agents, baselines
B1/B2, the reviewer UI, and the full evaluation harness from B12 (including the
compliance-question rubric test). Those are Phase 2.

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

# run the end-to-end baseline workflow on the sample logs
python eval/run_baseline.py
```

`run_baseline.py` prints per-run predictions and accuracy, and writes full
results to `results/baseline_b0_results.json`.

## Data

`data/sample_logs/` holds three small **synthetic** logs used for the smoke
test above - see `data/sample_logs/README.md` for how to point the harness at
the real Who&When benchmark instead.

## Layout

```
src/agentledger/
  schema.py          normalised Event/RunLog model
  ingestion.py        log-format -> RunLog
  ledger.py           hash-chain Integrity Ledger
  controls.py         ISO/IEC 42001 + NIST AI RMF control catalogue
  tools.py             read_span / search_log / get_provenance / verify_chain / check_control
  providers.py         LLM provider interface (mock / hosted)
  baselines/
    b0_single_call.py  baseline B0
data/sample_logs/      synthetic smoke-test logs
eval/run_baseline.py   end-to-end workflow
tests/                 pytest suite
doc/                   Phase 1 literature review, gaps & proposal (.docx)
```
