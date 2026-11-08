# Paper outline + evidence notes (bullets only — NOT paper text)

Purpose: a section-by-section map of what each part of `paper/main.tex` needs to say, with the facts,
numbers and source files behind each point. Every number is from a file in `results/`. Write the actual
sentences yourselves (brief: AI-written prose is disqualifying; Turnitin report is mandatory).
Mark who writes each section: [A] Areej, [Ar] Armish, [both].

## Abstract [both, write last, 150-250 words]
- Problem: agent logs are unstructured, findings have no evidence, logs can be altered, no link to controls.
- Method: 3 gaps -> evidence-bound attribution, tamper-evident ledger + provenance, control-mapped checks.
- Headline results (pick 3-4): 0% unsupported claims with Verifier vs 56.3% without; 100%/0% tamper
  detection/false alarms with anchor (75.0% chain alone); Policy Checker F1 1.00 synthetic but real-data
  CTRL-07 precision 78%/recall 100%; accuracy on par with base paper (40/20 vs 40/25), not better.
- Say plainly it is a n=20 subset for Gap 1.

## 1. Introduction [both]
- Motivation: agentic systems fail in long multi-agent logs; auditors need evidence, integrity, compliance mapping.
- Base paper (Who&When): attribution accuracy only, bare labels, no evidence, no integrity.
- Three gaps (Phase 1 doc, `doc/Agentic Phase 1 (fixed).docx`): G1 evidence, G2 integrity, G3 control mapping.
- Contributions list (3-4 bullets): citing+verifying agent loop; PROV-linked hash-chain ledger + tamper
  harness; 6/12 control predicates + Policy Checker + 80-case suite validated against real data; honest
  negative/partial findings.

## 2. Related work [both]
- Source: Phase 1 lit review (section A3). Group by: failure attribution (Who&When, TRAIL), LLM-as-judge /
  verification, tamper-evident logging / provenance (W3C PROV), governance standards (ISO/IEC 42001, NIST AI RMF).
- Positioning sentence per group: what prior work lacks that we add.
- Check `paper/references.bib` has every citation you use.

## 3. Problem formulation [both]
- Input: normalised RunLog (events: id, step, agent, role, content, tool_calls, timestamp). Output: AuditFinding
  (agent, step, cited_record_ids, verified, control results).
- Hypotheses from Phase 1: H1 unsupported claims <5%; H2 (Gap 2) 100% tamper detection, 0 false alarms,
  <10 ms/event; H3 control-level precision/recall.
- Metrics: agent/step accuracy, unsupported-claim rate, detection/false-alarm/overhead, P/R/F1 per control.

## 4. Methodology
### 4.1 Architecture [Ar] — ingestion -> ledger -> Retriever -> Auditor -> Verifier -> Policy Checker; `orchestrator.py`; ledger gates "verified"; ablation switches use_verifier/use_policy_checker.
### 4.2 Gap 1 [Ar]
- Retriever: keyword + tail-window shortlist (not whole log). Auditor: proposes agent/step citing record ids.
- Verifier: re-reads only cited records, rejects unsupported claims, one revision pass.
- Known limitation: keyword retriever misses claims without error words (`results/failure_analysis_gap1.md`).
### 4.3 Gap 2 [A] — the section you write
- Ledger: SHA-256 chain, entry hash = H(prev_hash || canonical JSON payload); genesis hash.
- Payload covers the FULL event (content, role, agent, step, timestamp, tool calls) — contrast with the
  narrower payload in `eval/run_system.py:_build_ledger` (event_id/agent/tool_calls only).
- Provenance (`src/agentledger/provenance.py`): PROV mapping — Agent, Entity(event), Activity(tool call),
  input/output entities with digests; relations wasAttributedTo, wasDerivedFrom, used, wasInformedBy,
  wasGeneratedBy. Links live inside the hashed payload (so editing a link is tampering). Graph is rebuilt from
  the ledger, never a second source of truth.
- Verification modes: (1) chain; (2) chain + graph consistency; (3) + external anchor (head hash + length).
- Index fix: index not hashed originally -> verify() now checks index == position.
- Why anchor: truncation and full re-hash are undetectable by chain alone.
### 4.4 Gap 3 [Ar] — 12 controls declared mapped to ISO 42001 / NIST AI RMF; 6 implemented (CTRL-01,02,03,06,07,11); 6 skipped with stated reason (org-level evidence a log cannot contain); Policy Checker skips unimplemented, never silently passes.

## 5. Experimental setup [both]
- Data: real Who&When, 184 logs (58 Hand-Crafted + 126 Algorithm-Generated). Gap 1/E1-E3/E5 on a 20-log subset
  (first 10+10 by file order, not hand-picked) due to free-tier quota. Gap 2 on all 184. Gap 3 suite: 80
  synthetic cases + real-data check on 184.
- Models: free Groq `openai/gpt-oss-120b` after automatic fallback from `qwen/qwen3.8-27b`; OpenRouter second source.
- Baselines: B0 single LLM call (own), B1 base-paper `all_at_once` (adapted from reference repo; `step_by_step`
  / others — state which were/weren't run, see main.tex line ~200).
- Honesty note: test set not used for tuning; Verifier/CTRL-07 recalibration done on small dev samples (see devlog).
- Reproduce: commands in README "Running it".

## 6. Evaluation methodology [both] — define each metric precisely; unsupported-claim rate = verified-but-wrong / verified; tamper detection = flagged / applied tamper cases; false alarm = clean ledgers flagged.

## 7. Results
### Gap 1 / E1-E3 [Ar] (`results/gap_resolution_table_gap1_gap3.md`)
| | agent acc | step acc |
|---|---|---|
| E1 B0 | 50.0% | 5.0% |
| E2 B1 all_at_once | 40.0% | 25.0% |
| E3 ours | 40.0% | 20.0% |
- Unsupported-claim rate: 0.0% (1/1 verified) vs 56.3% (9/16) without Verifier (`gap1_ablation_summary.json`).
- Verified rate only ~5% of claims (precision high, recall very low).
### Gap 2 / E4 [A] (`results/tamper_results_real184.json`, `gap2_tamper_validation.md`)
| mode | detection | false alarms |
|---|---|---|
| chain | 75.0% | 0/184 |
| chain+graph | 82.5% | 0/184 |
| anchored | 100% | 0/184 |
- 184 logs, 4,092 events, 6,624 tamper cases, 13 types, seed 0. Overhead ~0.052 ms append + ~0.051 ms verify per event.
- Per-type: all payload edits/deletes/reorders/inserts/index edits 100% by chain; truncate_tail and edit_rechain
  0% by chain; delete_rechain 499/552 by graph.
- Pre-fix finding: index-only edits 0/43 (synthetic) before fix -> `tamper_results_before_index_fix.json`.
- Secondary: synthetic 83 logs, 779 cases: 78.3 / 81.6 / 100%.
### Gap 3 / E4 [Ar]
- Synthetic suite: CTRL-03/06/07/11 P=R=F1=1.00 (80 cases) — deterministic rules scored on own patterns.
- Real data (`gap3_real_violation_validation.md`): CTRL-03/11 zero real triggers (0/184); CTRL-07 triggers 145/184,
  benign `UserWarning` noise caused false positives; after fix real precision 78% / recall 100% (n=9 genuine).
### Gap-resolution table [both] — copy from `results/gap_resolution_table.md` (auto-generated) for all 3 gaps.

## 8. Ablation & efficiency [Ar mostly; A adds Gap 2]
- E5: Verifier removed -> unsupported-claim rate 0% -> 56.3%; accuracy 40/20 vs 35/5.
- E6 (`results/e6_efficiency.md`): system 3.35 calls/run vs 1.0; 1,114.6 s vs 382-449 s total; 2.6x prompt volume.
- Gap 2 cost: ~0.10 ms/event, negligible vs LLM latency (~16-22 s/call).
- Reliability: free-tier quota exhaustion, fallback chain bugs found+fixed, n=40 attempt failed 18/40 from combined quota.
- Gap 2 ablation = the three verification modes above.
- No-integrity baseline: 0% by construction (state as such, or measure it).

## 9. Failure analysis [Ar, A adds Gap 2]
- Gap 1 categories (n=20): 40% incorrect abstention ("unknown"), 15% wrong agent (Orchestrator bias), 20% right
  agent wrong step, 20% fully correct, 5% infra error. 0 of 4 correct predictions were verified.
- Cases: retriever misses claims without error keywords (d1af70ea…); long-log orchestrator bias (0a65cb96…, 93 events).
- Gap 3: harness-noise false positive found by hand-labeling real logs.
- Gap 2 [A]: index-not-hashed bug found by harness; narrow payload in run_system.py; undetectable-by-construction attacks.

## 10. Limitations & threats [both]
- Gap 1 numbers n=20, directional only; full-184 run not available (check for `*_full184.json`).
- Accuracy not better than base paper; Verifier recall very low (~5% verified).
- Gap 3: 6/12 controls; synthetic F1=1.00 not representative; CTRL-03/11 untestable on this benchmark.
- Gap 2 [A]: tampering injected by us, not a real adversary; anchor trust assumed; no concurrency/storage attacks;
  real logs have no tool calls so tool-result tampering untested on real data; short logs in synthetic set.
- Model is a free-tier open model, results may differ with other models; single seed.

## 11. Conclusion & future work [both]
- Main finding: evidence-bound verification gives a trustworthy-when-verified signal; ledger gives cheap tamper
  evidence given an anchor; control checks are shallow but real-validated.
- Future: relax Verifier threshold and re-measure; embedding-based retriever; external anchor/signed timestamps;
  remaining 6 controls; full-184 run; real-adversary tamper evaluation.

## Open items before submission
- `paper/main.tex` line 292: which gap's ablation is that marker? Ask Armish.
- Replace all `[[WRITE THIS]]` / `[[Areej: ...]]` markers with your own prose; keep tables as filled in.
- Re-run `python eval/aggregate_results.py` if any result changes; never hand-type numbers.
- Check overnight full-184 files before citing n=20 as the final numbers.
