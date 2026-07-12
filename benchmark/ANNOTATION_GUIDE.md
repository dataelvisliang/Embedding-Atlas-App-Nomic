# Annotation Guide

Annotators must not see system names, ranks, model scores, utility, or stopping decisions. Use only the query, review text, and region samples in the blind pool.

## Item relevance

Assign one label per review:

- `2` — directly satisfies the semantic intent and all observable hard constraints.
- `1` — partially relevant; matches the central intent but misses a soft facet, or the evidence is incomplete.
- `0` — irrelevant, contradicted, or violates a hard constraint.

Assign one concise canonical `theme` to relevant items. Reuse an existing label when two items express the same theme; do not create synonyms merely because wording differs.

## Region purity

Estimate the proportion of sampled reviews supporting one dominant coherent semantic theme:

- `0.90–1.00` — nearly every sample supports the same theme.
- `0.70–0.89` — strong majority with limited outliers.
- `0.40–0.69` — mixed region with a visible but non-dominant theme.
- `0.10–0.39` — weak coherence.
- `0.00–0.09` — empty, contradictory, or no meaningful common theme.

Purity is independent of the query. A coherent Champagne region can have high purity even when the query asks for earthy red wine.

## Region intent match

Estimate how strongly the region samples satisfy the query intent and hard constraints:

- `0.90–1.00` — nearly all evidence directly satisfies the intent.
- `0.70–0.89` — strong majority support.
- `0.40–0.69` — partial or mixed support.
- `0.10–0.39` — weak support.
- `0.00–0.09` — absent, contradicted, or violates hard constraints.

## Procedure

1. Read the query and its explicit constraints.
2. Label each item without looking at other systems.
3. Label each region from all provided samples, not its generated category name.
4. Add a note only for ambiguity, missing evidence, or constraint conflicts.
5. Each unit needs at least two independent annotators.
6. Resolve disagreements larger than one relevance grade or `0.30` on a region score through adjudication.

Never use the model's `purity`, `intent_match`, or `projection_agreement` as annotation evidence.
