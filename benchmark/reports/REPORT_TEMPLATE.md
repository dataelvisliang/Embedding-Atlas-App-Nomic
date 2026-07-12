# Wine PAR Benchmark Report

## Reproducibility

- Git commit:
- Dataset checksum:
- Projection checksum and UMAP parameters:
- Embedding model:
- Orchestrator model:
- Analyzer model:
- Benchmark manifest:
- Seeds: 17, 29, 43

## Main results

Report mean and 95% bootstrap confidence intervals for nDCG@10, Precision@10, pooled Recall@10, theme coverage, success rate, tokens, latency, tool calls, and probes.

## Results by task

Separate exact, semantic, exploration, and comparison queries. Do not present only the aggregate score.

## Calibration

Report purity and intent-match MAE, Spearman correlation, and reliability plots against human region judgments.

## Search behavior

Report accepted/refined/resampled/rejected branches, duplicate-action blocks, stop reasons, over-search, under-search, and time to first relevant result.

## Ablations

Include every ablation listed in `RUNBOOK.md` under equal budgets.

## Limitations

Discuss pooled-judgment incompleteness, LLM annotation risks, UMAP distortion, query-set size, wine-domain specificity, model variance, and cost differences.
