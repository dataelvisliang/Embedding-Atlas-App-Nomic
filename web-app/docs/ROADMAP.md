# Wine Atlas Agent Roadmap

## Current system

- React chat integrated with the Embedding Atlas selection state.
- DuckDB-WASM over the local Parquet dataset.
- Sommelier orchestrator plus specialized review Analyzer.
- Projection-guided agent loop with coarse scan, parallel circular probes, refinement, comparison, and category-card memory.
- Structured tool inputs; unrestricted SQL is no longer exposed to the LLM.
- Per-region `projection_agreement` diagnostic using stored high-dimensional neighbors.
- Enforced per-request budgets, geometric deduplication, no-progress stopping, and inspectable policy trajectories.
- Objective-aware semantic stopping, candidate utility ranking, explicit branch states, and calibrated resampling stability.

## Live tools

| Tool | Status | Purpose |
| --- | --- | --- |
| `search_reviews` | Complete | Known lexical and metadata constraints |
| `scan_regions` | Complete | Coarse density-based candidate regions |
| `inspect_regions` | Complete | Parallel circular probes and Analyzer summaries |
| `refine_region` | Complete | Coarse-to-fine children inside a parent circle |
| `compare_regions` | Complete | Consistent regional statistics |
| `save_results` | Complete | Verified category-card memory |

## Research/evaluation work

- [ ] Persist complete trajectories with latency and token usage (tool order and stopping reason are already recorded in memory).
- [ ] Add ANN-only, XY-only, lexical, and hybrid baselines.
- [ ] Evaluate Recall@k, nDCG, MRR, thematic coverage, diversity, and task completion.
- [ ] Ablate projection access, spatial tools, and human map interaction.
- [ ] Test UMAP seeds/parameters and alternative projections.
- [ ] Add at least one non-wine dataset.
- [ ] Scale experiments from 10k to 1M items.

## Product work

- [ ] Draw Agent probe circles and trajectories directly on the map.
- [ ] Let users approve, move, resize, and lasso Agent regions.
- [ ] Persist exploration sessions and export trajectories.
- [ ] Add explicit time/tool/token budgets to the stopping policy.
- [ ] Add semantic ANN verification when full embedding vectors are available in the browser.

See [Projection-Guided Agentic Search](PROJECTION_AGENT_SEARCH.md) for the method definition and [Architecture](ARCHITECTURE.md) for the implementation.
