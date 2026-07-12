#!/usr/bin/env python3
"""Convert an extracted browser SearchPolicy export into a benchmark run JSONL record."""
from __future__ import annotations

import argparse
import json
from pathlib import Path


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("trajectory", type=Path)
    parser.add_argument("--query-id", required=True)
    parser.add_argument("--system-id", default="par_v1")
    parser.add_argument("--seed", type=int, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()

    data = json.loads(args.trajectory.read_text(encoding="utf-8"))
    candidates = sorted(data.get("candidates", []), key=lambda row: row.get("utility", 0), reverse=True)
    accepted = [row for row in candidates if row.get("recommended_action") == "accept"]

    review_metadata = {}
    for entries in data.get("saved_categories", {}).values():
        for category in entries:
            for review in category.get("reviews", []):
                review_metadata[int(review["id"])] = review

    ranked_ids = []
    for candidate in accepted:
        for review_id in candidate.get("review_ids", []):
            review_id = int(review_id)
            if review_id not in ranked_ids:
                ranked_ids.append(review_id)

    results = []
    for rank, review_id in enumerate(ranked_ids, 1):
        review = review_metadata.get(review_id, {})
        candidate = next((row for row in accepted if review_id in row.get("review_ids", [])), {})
        results.append({
            "review_id": review_id,
            "rank": rank,
            "score": candidate.get("utility"),
            "region_id": candidate.get("id"),
            "theme": candidate.get("category"),
            "title": review.get("title"),
            "description": review.get("text") or review.get("description") or review.get("excerpt"),
        })

    regions = [{
        "region_id": candidate["id"],
        "purity": candidate["purity"],
        "intent_match": candidate["intent_match"],
        "utility": candidate["utility"],
        "recommended_action": candidate["recommended_action"],
        "review_ids": candidate.get("review_ids", []),
        "samples": [review_metadata[review_id] for review_id in candidate.get("review_ids", []) if review_id in review_metadata],
    } for candidate in candidates]

    remaining = data.get("remaining", {})
    record = {
        "query_id": args.query_id,
        "system_id": args.system_id,
        "seed": args.seed,
        "results": results,
        "regions": regions,
        "cost": {
            "latency_ms": data.get("elapsed_ms", 0),
            "total_tokens": max(0, 80000 - remaining.get("modelTokens", 80000)),
            "tool_calls": max(0, 18 - remaining.get("toolCalls", 18)),
            "probes": data.get("inspected_region_count", 0),
        },
        "stop_reason": data.get("stop_reason"),
        "trajectory": data.get("trajectory", []),
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    with args.output.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(record, ensure_ascii=False) + "\n")
    print(f"Appended {args.query_id}/{args.system_id}/seed-{args.seed} to {args.output}")


if __name__ == "__main__":
    main()
