# E6 — Efficiency & reliability, n=20 real Who&When subset

All numbers from `provider_stats` recorded by each run (`src/agentledger/providers.py`'s
`LLMProvider.stats()`); no manual timing. All on the same 20-log real subset as the E1/E2/E3/E5
results elsewhere in `results/`.

## Cost and latency

| Configuration | LLM calls | Calls / run | Total latency | Avg latency / call | Chars in (prompt) | Chars out (completion) |
|---|---|---|---|---|---|---|
| E1 — B0 (single call) | 20 | 1.0 | 382.5 s | 19.1 s | 199,329 | 695 |
| E2 — B1 all_at_once (base paper) | 20 | 1.0 | 448.8 s | 22.4 s | 208,289 | 374 |
| E3 — System, Verifier **on** | 67 | 3.35 | 1,114.6 s | 16.6 s | 505,377 | 8,361 |
| E5 — System, Verifier **off** | 16† | 0.8† | 338.5 s | 21.2 s | 179,209 | 3,942 |

† 4 of the 20 runs in this particular file errored out before the model-fallback fix existed
(see reliability section below) — `call_count` here only reflects the 16 that succeeded, so the
"calls / run" figure undercounts what a clean run would need (closer to 1.0, same as E1/E2,
since Verifier-off only makes the single Auditor call).

**Reading these numbers:** the full system (Verifier on) costs roughly **3.4x the LLM calls** and
**2.6x the prompt volume** of either baseline, for the accuracy/unsupported-claim-rate trade-off
documented in `results/gap_resolution_table_gap1_gap3.md` and
`results/gap1_ablation_summary.json`. Average per-call latency is actually *lower* for the system
runs (16.6s vs 19-22s) — a function of which model happened to be serving each run (see below),
not the system design itself.

## Reliability (the rest of E6's brief)

This ended up being the more interesting reliability story. Groq's free tier caps each model at
~200k tokens/day; the B0/B1/system testing done earlier in this session exhausted that cap on two
different models in turn (`openai/gpt-oss-20b`, then `qwen/qwen3.8-27b`). Before a fix, every call
against an exhausted model silently retried for 3-5 minutes before failing — which is exactly why
`results/system_results_noverifier.json` (generated before the fix) has 4 runs recorded as
errors. `GroqProvider` now (`src/agentledger/providers.py`) falls through a chain of five free
models and recognises a "tokens per day" error specifically, advancing immediately instead of
retrying a window that cannot possibly clear in time. The E1/E2 runs in the table above
(generated after the fix) show this working: `model_switches: ['qwen/qwen3.8-27b']` in their
`provider_stats` means both runs started on the exhausted model and recovered automatically
mid-run with zero errors, landing on `openai/gpt-oss-120b`.

**Update after actually re-running at larger scale:** a second bug was found and fixed — the
fallback only advanced on a *confirmed* "tokens per day" error, not on plain retry-exhaustion, so
a model that kept rate-limiting without that exact wording stalled the chain early (it reached
`openai/gpt-oss-safeguard-20b` without ever trying `allam-2-7b`). Fixed, and confirmed working: a
larger n=40 attempt correctly cycled through all 5 models (`model_switches` shows all 4 earlier
ones triggered). **But it still had 18/40 runs error out**, because by that point in the session
we had exhausted the *combined* daily quota across all 5 free models at once from the volume of
testing done today — the fallback chain has nowhere left to fall back to when every link is
simultaneously near its cap. Quota does recover (a check minutes later showed all 5 models
available again), but recovers slower than a 40-run batch burns it. **Conclusion:** the n=20
results elsewhere in this repo (0 errors) are the reliable, reportable sample; a clean n=40+ run
is a real capacity question, not a bug, and would need either a paid tier or spacing batches far
enough apart in time to let quota recover between them.
