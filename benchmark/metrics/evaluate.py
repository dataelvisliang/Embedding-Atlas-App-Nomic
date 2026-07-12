#!/usr/bin/env python3
"""Dependency-free benchmark evaluator for ranked retrieval, exploration, cost, and calibration."""
from __future__ import annotations

import argparse
import json
import math
import statistics
from collections import defaultdict
from pathlib import Path


def read_jsonl(path: Path):
    if not path.exists():
        return []
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def mean(values):
    values = [value for value in values if value is not None and math.isfinite(value)]
    return statistics.fmean(values) if values else None


def dcg(grades):
    return sum((2 ** grade - 1) / math.log2(rank + 2) for rank, grade in enumerate(grades))


def average_ranks(values):
    order = sorted(range(len(values)), key=lambda index: values[index])
    ranks = [0.0] * len(values)
    cursor = 0
    while cursor < len(order):
        end = cursor
        while end + 1 < len(order) and values[order[end + 1]] == values[order[cursor]]:
            end += 1
        rank = (cursor + end) / 2 + 1
        for position in range(cursor, end + 1):
            ranks[order[position]] = rank
        cursor = end + 1
    return ranks


def spearman(pairs):
    if len(pairs) < 2:
        return None
    left, right = zip(*pairs)
    x, y = average_ranks(left), average_ranks(right)
    mx, my = mean(x), mean(y)
    numerator = sum((a - mx) * (b - my) for a, b in zip(x, y))
    denominator = math.sqrt(sum((a - mx) ** 2 for a in x) * sum((b - my) ** 2 for b in y))
    return numerator / denominator if denominator else None


def aggregate_judgments(rows):
    grouped = defaultdict(list)
    for row in rows:
        grouped[(row["query_id"], row["unit_type"], row["unit_id"])].append(row)
    aggregated = {}
    for key, group in grouped.items():
        aggregated[key] = {
            "relevance": mean([row.get("relevance") for row in group]),
            "purity": mean([row.get("purity") for row in group]),
            "intent_match": mean([row.get("intent_match") for row in group]),
            "theme": next((row.get("theme") for row in group if row.get("theme")), None),
            "annotators": len({row["annotator_id"] for row in group}),
        }
    return aggregated


def item_metrics(run, query, judgments, cutoffs):
    qid = run["query_id"]
    results = sorted(run.get("results", []), key=lambda row: row["rank"])
    grades = [judgments.get((qid, "item", f"review-{row['review_id']}"), {}).get("relevance", 0) or 0 for row in results]
    all_relevant = {
        int(unit_id.removeprefix("review-"))
        for (query_id, unit_type, unit_id), value in judgments.items()
        if query_id == qid and unit_type == "item" and (value.get("relevance") or 0) > 0
    }
    retrieved_themes = []
    for result, grade in zip(results, grades):
        value = judgments.get((qid, "item", f"review-{result['review_id']}"), {})
        if grade > 0 and value.get("theme"):
            retrieved_themes.append(value["theme"])
    all_themes = {
        value["theme"] for (query_id, unit_type, _), value in judgments.items()
        if query_id == qid and unit_type == "item" and (value.get("relevance") or 0) > 0 and value.get("theme")
    }
    metrics = {
        "mrr": next((1 / (index + 1) for index, grade in enumerate(grades) if grade > 0), 0.0),
        "theme_coverage": len(set(retrieved_themes)) / len(all_themes) if all_themes else None,
        "theme_diversity": len(set(retrieved_themes)) / len(retrieved_themes) if retrieved_themes else 0.0,
        "success_rate": float(sum(grade > 0 for grade in grades) >= query["target_count"]),
    }
    for cutoff in cutoffs:
        top = grades[:cutoff]
        ideal = sorted([value["relevance"] or 0 for (query_id, unit_type, _), value in judgments.items() if query_id == qid and unit_type == "item"], reverse=True)[:cutoff]
        metrics[f"precision@{cutoff}"] = sum(grade > 0 for grade in top) / cutoff
        metrics[f"recall@{cutoff}"] = len({result["review_id"] for result, grade in zip(results[:cutoff], top) if grade > 0}) / len(all_relevant) if all_relevant else None
        ideal_dcg = dcg(ideal)
        metrics[f"ndcg@{cutoff}"] = dcg(top) / ideal_dcg if ideal_dcg else None
    return metrics


def load_region_source_map(path: Path | None):
    if not path or not path.exists():
        return {}
    sources = json.loads(path.read_text(encoding="utf-8"))
    mapping = {}
    for pooled_key, records in sources.items():
        query_id, unit_id = pooled_key.split(":", 1)
        for record in records:
            if "region_id" in record:
                mapping[(query_id, record["system_id"], record["seed"], record["region_id"])] = unit_id
    return mapping


def summarize(records, metric_names):
    return {metric: mean([record.get(metric) for record in records]) for metric in metric_names}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--runs", type=Path, required=True)
    parser.add_argument("--judgments", type=Path, required=True)
    parser.add_argument("--queries", type=Path, default=Path("benchmark/queries/queries_v1.jsonl"))
    parser.add_argument("--pool-sources", type=Path)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--split", choices=["dev", "test", "all"], default="all")
    args = parser.parse_args()

    queries = {row["query_id"]: row for row in read_jsonl(args.queries)}
    judgments = aggregate_judgments(read_jsonl(args.judgments))
    runs = [row for path in sorted(args.runs.glob("*.jsonl")) for row in read_jsonl(path)]
    if args.split != "all":
        runs = [run for run in runs if queries[run["query_id"]]["split"] == args.split]
    source_map = load_region_source_map(args.pool_sources)
    cutoffs = [5, 10, 20]
    records = []
    calibration = defaultdict(lambda: {"purity": [], "intent_match": []})

    for run in runs:
        query = queries[run["query_id"]]
        row = {
            "query_id": run["query_id"], "system_id": run["system_id"], "seed": run["seed"],
            "split": query["split"], "task_type": query["task_type"],
            **item_metrics(run, query, judgments, cutoffs),
            "latency_ms": run["cost"]["latency_ms"], "tokens": run["cost"]["total_tokens"],
            "tool_calls": run["cost"]["tool_calls"], "probes": run["cost"]["probes"],
        }
        records.append(row)
        for region in run.get("regions", []):
            unit_id = source_map.get((run["query_id"], run["system_id"], run["seed"], region["region_id"]), region["region_id"])
            truth = judgments.get((run["query_id"], "region", unit_id))
            if truth:
                for metric in ("purity", "intent_match"):
                    if truth.get(metric) is not None:
                        calibration[run["system_id"]][metric].append((float(region[metric]), float(truth[metric])))

    metric_names = ["mrr", "theme_coverage", "theme_diversity", "success_rate", "latency_ms", "tokens", "tool_calls", "probes"]
    metric_names += [f"{metric}@{cutoff}" for cutoff in cutoffs for metric in ("precision", "recall", "ndcg")]
    by_system = {}
    for system_id in sorted({record["system_id"] for record in records}):
        system_records = [record for record in records if record["system_id"] == system_id]
        by_system[system_id] = summarize(system_records, metric_names)
        for metric in ("purity", "intent_match"):
            pairs = calibration[system_id][metric]
            by_system[system_id][f"{metric}_mae"] = mean([abs(predicted - actual) for predicted, actual in pairs])
            by_system[system_id][f"{metric}_spearman"] = spearman(pairs)

    by_task = {}
    for system_id in sorted({record["system_id"] for record in records}):
        by_task[system_id] = {}
        for task_type in sorted({record["task_type"] for record in records}):
            subset = [record for record in records if record["system_id"] == system_id and record["task_type"] == task_type]
            if subset:
                by_task[system_id][task_type] = summarize(subset, metric_names)

    output = {"split": args.split, "run_count": len(records), "by_system": by_system, "by_task": by_task, "per_run": records}
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(output, indent=2) + "\n", encoding="utf-8")

    markdown = ["# Benchmark Results", "", f"Split: `{args.split}` — {len(records)} runs", "", "| System | nDCG@10 | P@10 | Coverage | Success | Tokens | Latency ms |", "| --- | ---: | ---: | ---: | ---: | ---: | ---: |"]
    for system_id, values in by_system.items():
        fmt = lambda key: "—" if values.get(key) is None else f"{values[key]:.3f}"
        markdown.append(f"| {system_id} | {fmt('ndcg@10')} | {fmt('precision@10')} | {fmt('theme_coverage')} | {fmt('success_rate')} | {fmt('tokens')} | {fmt('latency_ms')} |")
    args.output.with_suffix(".md").write_text("\n".join(markdown) + "\n", encoding="utf-8")
    print(f"Evaluated {len(records)} runs; wrote {args.output} and {args.output.with_suffix('.md')}")


if __name__ == "__main__":
    main()
