# Projection-Guided Agentic Search

The Atlas agent treats the UMAP projection as an operational search space rather than a visualization-only artifact.

## Research assumption

Points that are close in the 2D projection are candidates for semantic similarity. This is a probabilistic assumption, not ground truth: UMAP can introduce false neighbors, tear high-dimensional neighborhoods apart, and distort density. Region results therefore include a `projection_agreement` diagnostic computed from the stored high-dimensional k-neighbor graph.

## Search loop

1. **Structured retrieval** handles known terms and metadata constraints.
2. **Coarse scan** bins the projection and proposes dense candidate regions.
3. **Parallel probes** place up to eight circular regions in one action.
4. **Observation** returns density, sampled themes, semantic purity, intent match, representative reviews, and projection agreement.
5. **Adaptive action** keeps, rejects, compares, or refines regions based on the observation.
6. **Stopping** occurs when evidence is sufficient, results repeat, or further probes are unlikely to change the answer.
7. **Saving** is a separate UI-memory action performed only after verification.

This workflow is agentic when later probes depend on earlier observations. A fixed one-shot batch of circles is parallel spatial retrieval, not the complete agentic loop.

## Enforced search policy

`SearchPolicy` makes the traversal reproducible instead of relying on prompt compliance. Each user request starts a fresh policy session with these default ceilings:

| Resource | Limit |
| --- | ---: |
| Tool actions | 18 |
| Coarse scans | 2 |
| Structured searches | 4 |
| Inspected circles | 24 |
| Refinements | 5 |
| Comparisons | 4 |
| Saved categories | 8 |
| Model tokens (orchestrator + Analyzer) | 80,000 |
| Wall-clock exploration time | 120 seconds |

The controller canonicalizes scan/refine/compare parameters, rejects duplicate actions, and treats circles as duplicates when their centers are within 25% of the smaller radius and their radius ratio is at most 1.25. Oversized probe batches are truncated to the remaining circle budget. Two consecutive policy-blocked retries force convergence so a non-compliant model cannot spin until the iteration ceiling.

Themes and category labels returned by each probe round are accumulated as discovery signals, but only themes from circles with `intent_match >= 0.75` count as relevant progress. Two consecutive probe rounds with no new relevant theme lock spatial search. After locking, the controller allows only `save_results` followed by the final answer.

Before every LLM step, the controller injects `SEARCH_POLICY_STATE`, including remaining budgets, discovered themes, recent events, and the stop reason. The UI displays live probe/theme/action/token/time counts. The full parameterized trajectory is emitted to the browser console and included in downloaded chat Markdown for experiment capture.

## Tool boundaries

| Tool | Responsibility | Does not do |
| --- | --- | --- |
| `search_reviews` | Known lexical and metadata retrieval | Spatial exploration |
| `scan_regions` | Coarse grid candidate generation | Theme interpretation |
| `inspect_regions` | Batch circular sampling and Analyzer interpretation | Global scanning |
| `refine_region` | Propose smaller children inside a promising circle | Interpret the children |
| `compare_regions` | Quantitative contrast with consistent metrics | Save results |
| `save_results` | Persist verified IDs for UI cards | Retrieval |

DuckDB SQL is an implementation detail. The Agent receives structured parameters instead of an unrestricted SQL tool.

## Geometry

`scan_regions` uses square grid cells because they are cheap to aggregate and cache. The returned cell center and suggested radius become proposals for `inspect_regions`, which uses a true circle:

```text
(projection_x - center_x)^2 + (projection_y - center_y)^2 <= radius^2
```

`refine_region` subdivides the bounding area of a selected parent circle and only counts points inside the parent. The Agent must inspect the returned child circles before treating them as semantic findings.

## Evaluation hooks

Every inspected region exposes enough information to log:

- candidate density and analyzed sample size;
- selected coordinates and radius;
- Analyzer themes and review IDs;
- `purity` (0-1): estimated share of the sample supporting one dominant coherent theme;
- `intent_match` (0-1): estimated strength of evidence satisfying the explicit user intent;
- projection agreement;
- number and order of scan, inspect, refine, and compare actions.

These fields support comparison against lexical search, high-dimensional ANN, XY-only retrieval, and hybrid agent baselines.

## Candidate utility and state transitions

Every inspected circle receives a controller-side utility:

```text
utility =
    0.45 * intent_match
  + 0.20 * purity
  + 0.15 * novelty
  + 0.10 * coverage_gain
  + 0.10 * confidence
  - 0.05 search_cost
```

`confidence` combines sample sufficiency with projection agreement. Projection agreement affects confidence, not relevance. The controller assigns an explicit next state:

| Intent match | Purity | State/action |
| ---: | ---: | --- |
| >= 0.75 | >= 0.70 | `accept` |
| >= 0.75 | < 0.70 | `refine` |
| 0.45-0.75 | >= 0.70 | `resample` once, then `compare` |
| 0.45-0.75 | < 0.70 | `explore` only when utility justifies cost |
| < 0.45 | any | `reject` |

Refinement requires the ID of a candidate in `refine` or `explore`; comparison requires at least two inspected, non-rejected IDs. Spatial review IDs can be saved only from `accept` candidates. A resampled candidate aggregates both score rounds and reports `score_stability`.

## Semantic stopping

The controller extracts a requested result count from explicit user wording when possible, otherwise targeting three accepted regions. Search stops when:

- the accepted-region target is met;
- enough accepted regions have purity >= 0.70;
- relevant-theme coverage reaches the target (capped at two themes);
- a requested comparison has actually executed;
- or two rounds add no new relevant theme;
- or the best remaining frontier utility falls below 0.15 after at least two probe rounds;
- or any hard action/token/time budget fires.
