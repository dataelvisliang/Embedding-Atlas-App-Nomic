#!/usr/bin/env python3
"""Validate benchmark queries, configs, runs, and judgments without third-party packages."""
from __future__ import annotations

import json
import hashlib
import sys
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
BENCH = ROOT / "benchmark"


def jsonl(path: Path):
    if not path.exists():
        return []
    rows = []
    for line_no, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
        if not line.strip():
            continue
        try:
            rows.append(json.loads(line))
        except json.JSONDecodeError as exc:
            raise ValueError(f"{path}:{line_no}: {exc}") from exc
    return rows


def require(condition: bool, message: str, errors: list[str]):
    if not condition:
        errors.append(message)


def main() -> int:
    errors: list[str] = []
    query_path = BENCH / "queries" / "queries_v1.jsonl"
    queries = jsonl(query_path)
    ids = [row.get("query_id") for row in queries]
    require(len(queries) == 30, f"expected 30 queries, found {len(queries)}", errors)
    require(len(ids) == len(set(ids)), "query_id values must be unique", errors)
    require(Counter(row.get("split") for row in queries) == {"dev": 10, "test": 20}, "expected 10 dev and 20 test queries", errors)
    allowed_tasks = {"exact", "semantic", "exploration", "comparison"}
    for row in queries:
        qid = row.get("query_id", "<missing>")
        for field in ("query", "intent", "target_count", "hard_constraints", "facets"):
            require(field in row, f"{qid}: missing {field}", errors)
        require(row.get("task_type") in allowed_tasks, f"{qid}: invalid task_type", errors)
        require(isinstance(row.get("target_count"), int) and row.get("target_count", 0) > 0, f"{qid}: invalid target_count", errors)

    systems = json.loads((BENCH / "configs" / "systems.json").read_text(encoding="utf-8"))
    system_ids = {system["system_id"] for system in systems}
    require(len(system_ids) == 7, "systems.json must contain seven unique baselines", errors)

    manifest = json.loads((BENCH / "frozen_manifest_v1.json").read_text(encoding="utf-8"))
    for relative, expected in manifest["files"].items():
        actual = hashlib.sha256((ROOT / relative).read_bytes()).hexdigest()
        require(actual == expected, f"frozen file changed: {relative}", errors)

    query_ids = set(ids)
    run_count = 0
    for path in sorted((BENCH / "runs").glob("*.jsonl")):
        for row in jsonl(path):
            run_count += 1
            require(row.get("query_id") in query_ids, f"{path}: unknown query_id {row.get('query_id')}", errors)
            require(row.get("system_id") in system_ids, f"{path}: unknown system_id {row.get('system_id')}", errors)
            results = row.get("results", [])
            ranks = [result.get("rank") for result in results]
            require(ranks == list(range(1, len(ranks) + 1)), f"{path}: ranks must be contiguous from 1", errors)
            review_ids = [result.get("review_id") for result in results]
            require(len(review_ids) == len(set(review_ids)), f"{path}: duplicate review_id in one ranking", errors)
            cost = row.get("cost", {})
            for field in ("latency_ms", "total_tokens", "tool_calls", "probes"):
                require(isinstance(cost.get(field), (int, float)) and cost[field] >= 0, f"{path}: invalid cost.{field}", errors)

    for row in jsonl(BENCH / "annotations" / "judgments.jsonl"):
        require(row.get("query_id") in query_ids, f"judgment references unknown query {row.get('query_id')}", errors)
        require(row.get("unit_type") in {"item", "region"}, "judgment unit_type must be item or region", errors)
        if row.get("unit_type") == "item":
            require(row.get("relevance") in {0, 1, 2}, "item relevance must be 0, 1, or 2", errors)
        else:
            for field in ("purity", "intent_match"):
                require(isinstance(row.get(field), (int, float)) and 0 <= row[field] <= 1, f"region {field} must be in [0,1]", errors)

    if errors:
        print("Benchmark validation failed:")
        print("\n".join(f"- {error}" for error in errors))
        return 1
    print(f"Benchmark valid: {len(queries)} queries, {len(system_ids)} systems, {run_count} run records")
    return 0


if __name__ == "__main__":
    sys.exit(main())
