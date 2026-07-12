# Benchmark Runbook

## 1. Freeze a system

Record the Git commit, model identifier, prompts, tool schema, projection artifact, dataset checksum, and system configuration. Do not modify thresholds between test queries.

## 2. Run systems

Run every system on the same query split and seeds `17`, `29`, and `43`. Enforce equivalent output depth and, for agent systems, record actual token, latency, tool, and probe costs.

Write one JSON object per `(query_id, system_id, seed)` to `benchmark/runs/<system_id>.jsonl`. The format is defined in `schemas/run.schema.json`.

For `par_v1`, download the completed chat, then convert it:

```powershell
python benchmark/scripts/extract_trajectory.py exported-chat.md --output benchmark/trajectories/wine-test-001-seed17.json
python benchmark/scripts/trajectory_to_run.py benchmark/trajectories/wine-test-001-seed17.json --query-id wine-test-001 --seed 17 --output benchmark/runs/par_v1.jsonl
```

Static systems should set agent-only costs such as `tool_calls` and `probes` to zero. Failed runs remain in the file with empty results and an explanatory `stop_reason`; do not silently rerun only unfavorable failures.

## 3. Pool blindly

```powershell
python benchmark/scripts/pool_candidates.py --runs benchmark/runs --output benchmark/annotations/pool.jsonl --depth 20
```

The pool hides system provenance in `pool.sources.json`. Do not give that file to annotators.

## 4. Annotate

Duplicate each pooled unit for at least two annotators. Store completed labels in `annotations/judgments.jsonl` following `schemas/judgment.schema.json` and `ANNOTATION_GUIDE.md`.

## 5. Validate

```powershell
python benchmark/scripts/validate.py
```

Resolve validation errors before evaluation.

## 6. Evaluate development data

```powershell
python benchmark/metrics/evaluate.py --runs benchmark/runs --judgments benchmark/annotations/judgments.jsonl --pool-sources benchmark/annotations/pool.sources.json --split dev --output benchmark/reports/dev_results.json
```

Threshold and prompt changes are allowed only here. Log every attempted configuration, not only the best one.

## 7. Evaluate frozen test data once

```powershell
python benchmark/metrics/evaluate.py --runs benchmark/runs --judgments benchmark/annotations/judgments.jsonl --pool-sources benchmark/annotations/pool.sources.json --split test --output benchmark/reports/test_results.json
```

Report all seven systems, all three seeds, failures, confidence intervals, per-task results, quality metrics, and cost metrics. A later system change requires a new version and fresh test evaluation.

## Required ablations

- Full `par_v1`.
- No XY access (`agent_ann`).
- XY without high-D diagnostic (`agent_xy`).
- No purity in utility.
- No intent match in utility.
- No refinement.
- No semantic stopping.
- Static XY retrieval without an agent.

The primary claim is supported only if improvements concentrate in exploration/comparison tasks and remain meaningful after accounting for token and latency cost.
