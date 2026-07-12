#!/usr/bin/env python3
"""Pool system outputs into a blind, deduplicated annotation file."""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path


def read_jsonl(path: Path):
    for line in path.read_text(encoding="utf-8").splitlines():
        if line.strip():
            yield json.loads(line)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--runs", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--depth", type=int, default=20)
    args = parser.parse_args()

    items: dict[tuple[str, int], dict] = {}
    regions: dict[tuple[str, str], dict] = {}
    sources: dict[str, list[dict]] = {}

    for path in sorted(args.runs.glob("*.jsonl")):
        for run in read_jsonl(path):
            query_id = run["query_id"]
            source = {"system_id": run["system_id"], "seed": run["seed"]}
            for result in run.get("results", [])[: args.depth]:
                review_id = int(result["review_id"])
                key = (query_id, review_id)
                unit_id = f"review-{review_id}"
                items.setdefault(key, {
                    "query_id": query_id,
                    "unit_type": "item",
                    "unit_id": unit_id,
                    "review_id": review_id,
                    "title": result.get("title"),
                    "description": result.get("description"),
                    "relevance": None,
                    "theme": None,
                    "annotator_id": None,
                    "notes": None,
                })
                sources.setdefault(f"{query_id}:{unit_id}", []).append({**source, "rank": result["rank"]})

            for region in run.get("regions", []):
                review_ids = sorted({int(value) for value in region.get("review_ids", [])})
                digest = hashlib.sha256(f"{query_id}:{review_ids}".encode()).hexdigest()[:12]
                unit_id = f"region-{digest}"
                key = (query_id, unit_id)
                regions.setdefault(key, {
                    "query_id": query_id,
                    "unit_type": "region",
                    "unit_id": unit_id,
                    "review_ids": review_ids,
                    "samples": region.get("samples", []),
                    "purity": None,
                    "intent_match": None,
                    "annotator_id": None,
                    "notes": None,
                })
                sources.setdefault(f"{query_id}:{unit_id}", []).append({**source, "region_id": region["region_id"]})

    rows = sorted([*items.values(), *regions.values()], key=lambda row: (row["query_id"], row["unit_type"], row["unit_id"]))
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text("".join(json.dumps(row, ensure_ascii=False) + "\n" for row in rows), encoding="utf-8")
    source_path = args.output.with_suffix(".sources.json")
    source_path.write_text(json.dumps(sources, indent=2) + "\n", encoding="utf-8")
    print(f"Wrote {len(rows)} blind units to {args.output}")
    print(f"Wrote hidden provenance to {source_path}")


if __name__ == "__main__":
    main()
