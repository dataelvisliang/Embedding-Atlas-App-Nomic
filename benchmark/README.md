# Projection-Augmented Retrieval Benchmark

This benchmark evaluates whether an LLM agent benefits from treating a 2D embedding projection as an operational search space.

Version `v1` contains 30 Wine Atlas queries across exact retrieval, semantic retrieval, open-ended exploration, and regional comparison. Ten development queries may be used for threshold tuning; twenty test queries are frozen for final reporting.

## Quick start

```powershell
python benchmark/scripts/validate.py
python benchmark/scripts/pool_candidates.py --runs benchmark/runs --output benchmark/annotations/pool.jsonl
python benchmark/metrics/evaluate.py --runs benchmark/runs --judgments benchmark/annotations/judgments.jsonl --output benchmark/reports/results.json
```

Do not tune utility weights, purity thresholds, prompts, or budgets on the test split. Any system change after observing test results requires a new benchmark version.

See [ANNOTATION_GUIDE.md](ANNOTATION_GUIDE.md) for blind labeling and [RUNBOOK.md](RUNBOOK.md) for the experiment protocol.
