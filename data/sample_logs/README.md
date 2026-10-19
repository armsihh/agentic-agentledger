# Sample logs

The three `*.json` files here are **synthetic**, hand-written smoke-test logs in the
Who&When-style format `ingestion.load_whowhen_log` expects. They exist so the
pipeline and test suite run end-to-end with no external downloads.

They are **not** the real Who&When benchmark. To evaluate against the real
benchmark, download the public release referenced in the Phase 1 proposal
(base paper [1]) and point `eval/run_baseline.py --logs <dir>` at it - no
code changes are needed as long as the files are converted to this same
`{run_id, turns: [...], ground_truth: {...}}` shape.
