#!/usr/bin/env python3
"""Prepare a human-readable calibration sheet from PAR pilot runs.

This is intentionally not the blind benchmark pool. It is a pilot-debugging
artifact: show the agent's accepted/frontier/high-scoring rejected regions,
attach sampled review text from the atlas parquet, and leave empty fields for a
human to judge whether the controller/analyzer thresholds are too strict.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import pandas as pd


DEFAULT_ACTIONS = ["accepted", "frontier", "rejected"]


def repo_root() -> Path:
    return Path(__file__).resolve().parents[2]


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def safe_float(value: Any) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return 0.0


def unit_id(query_id: str, region_id: str, review_ids: list[int]) -> str:
    digest = hashlib.sha256(f"{query_id}:{region_id}:{sorted(review_ids)}".encode()).hexdigest()[:12]
    return f"pilot-region-{digest}"


def review_lookup(df: pd.DataFrame) -> dict[int, dict[str, Any]]:
    rows: dict[int, dict[str, Any]] = {}
    id_columns = ["__row_index__", "id"]
    for _, row in df.iterrows():
        payload = {
            "review_id": int(row["__row_index__"]),
            "title": None if pd.isna(row.get("title")) else str(row.get("title")),
            "description": None if pd.isna(row.get("description")) else str(row.get("description")),
            "country": None if pd.isna(row.get("country")) else str(row.get("country")),
            "province": None if pd.isna(row.get("province")) else str(row.get("province")),
            "region_1": None if pd.isna(row.get("region_1")) else str(row.get("region_1")),
            "variety": None if pd.isna(row.get("variety")) else str(row.get("variety")),
            "winery": None if pd.isna(row.get("winery")) else str(row.get("winery")),
            "price": None if pd.isna(row.get("price")) else float(row.get("price")),
            "points": None if pd.isna(row.get("points")) else int(row.get("points")),
            "projection_x": None if pd.isna(row.get("projection_x")) else float(row.get("projection_x")),
            "projection_y": None if pd.isna(row.get("projection_y")) else float(row.get("projection_y")),
        }
        for column in id_columns:
            if column in row and not pd.isna(row[column]):
                rows[int(row[column])] = payload
    return rows


def compact_sample(sample: dict[str, Any], max_chars: int) -> dict[str, Any]:
    description = sample.get("description") or ""
    if len(description) > max_chars:
        description = description[: max_chars - 1].rstrip() + "…"
    return {**sample, "description": description}


def select_candidates(run: dict[str, Any], top_rejected: int) -> list[tuple[str, dict[str, Any]]]:
    selected: list[tuple[str, dict[str, Any]]] = []
    for action in ["accepted", "frontier"]:
        for candidate in run.get(action, []):
            selected.append((action, candidate))
    rejected = sorted(
        run.get("rejected", []),
        key=lambda item: (safe_float(item.get("intent_match")), safe_float(item.get("purity")), safe_float(item.get("utility"))),
        reverse=True,
    )
    for candidate in rejected[:top_rejected]:
        selected.append(("rejected", candidate))
    return selected


def build_rows(runs: list[dict[str, Any]], lookup: dict[int, dict[str, Any]], top_rejected: int, sample_chars: int) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for run in runs:
        query_id = run["query_id"]
        query = (run.get("pilot") or {}).get("query")
        for source_action, candidate in select_candidates(run, top_rejected):
            review_ids = [int(value) for value in candidate.get("review_ids", []) if str(value).isdigit()]
            samples = [compact_sample(lookup[review_id], sample_chars) for review_id in review_ids if review_id in lookup]
            row = {
                "query_id": query_id,
                "query": query,
                "unit_type": "region",
                "unit_id": unit_id(query_id, str(candidate.get("id")), review_ids),
                "region_id": candidate.get("id"),
                "source_action": source_action,
                "model_category": candidate.get("category"),
                "model_purity": candidate.get("purity"),
                "model_intent_match": candidate.get("intent_match"),
                "model_utility": candidate.get("utility"),
                "projection_agreement": candidate.get("projection_agreement"),
                "recommended_action": candidate.get("recommended_action"),
                "review_ids": review_ids,
                "samples": samples,
                "human_accept": None,
                "human_purity": None,
                "human_intent_match": None,
                "human_theme": None,
                "notes": None,
            }
            rows.append(row)
    return rows


def write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("".join(json.dumps(row, ensure_ascii=False) + "\n" for row in rows), encoding="utf-8")


def fmt(value: Any) -> str:
    if value is None:
        return "—"
    if isinstance(value, float):
        return f"{value:.3g}"
    return str(value)


def write_markdown(path: Path, rows: list[dict[str, Any]], source: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    grouped: dict[str, list[dict[str, Any]]] = {}
    for row in rows:
        grouped.setdefault(row["query_id"], []).append(row)

    lines = [
        "# PAR Pilot Calibration Sheet",
        "",
        f"Source run: `{source}`",
        "",
        "Use this for pilot calibration, not final blind evaluation. The model scores are shown so we can debug thresholds; final benchmark annotations should stay blind.",
        "",
        "Human fields to fill per region: `human_accept`, `human_purity`, `human_intent_match`, `human_theme`, `notes`.",
        "",
    ]
    for query_id, items in grouped.items():
        query = items[0].get("query") or ""
        lines.extend([f"## {query_id}", "", f"Query: {query}", ""])
        for index, row in enumerate(items, 1):
            lines.extend(
                [
                    f"### {index}. {row['region_id']} [{row['source_action']}]",
                    "",
                    f"- unit_id: `{row['unit_id']}`",
                    f"- model_category: {fmt(row['model_category'])}",
                    f"- model_purity / intent_match / utility: {fmt(row['model_purity'])} / {fmt(row['model_intent_match'])} / {fmt(row['model_utility'])}",
                    f"- projection_agreement: {fmt(row['projection_agreement'])}",
                    "- human_accept: ",
                    "- human_purity: ",
                    "- human_intent_match: ",
                    "- human_theme: ",
                    "- notes: ",
                    "",
                    "Samples:",
                    "",
                ]
            )
            for sample in row["samples"]:
                meta = " | ".join(
                    part
                    for part in [
                        f"id={sample['review_id']}",
                        fmt(sample.get("country")),
                        fmt(sample.get("province")),
                        fmt(sample.get("variety")),
                        f"points={fmt(sample.get('points'))}",
                        f"price={fmt(sample.get('price'))}",
                    ]
                    if part and part != "—"
                )
                lines.extend([f"- {meta}", f"  - {sample.get('title') or 'Untitled'}", f"  - {sample.get('description') or ''}", ""])
    path.write_text("\n".join(lines).rstrip() + "\n", encoding="utf-8")


def main() -> int:
    root = repo_root()
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run", type=Path, default=root / "benchmark" / "runs" / "pilot" / "par_pilot_20260712T153808Z.jsonl")
    parser.add_argument("--data", type=Path, default=root / "web-app" / "public" / "atlas" / "data" / "dataset.parquet")
    parser.add_argument("--output-jsonl", type=Path, default=root / "benchmark" / "reports" / f"pilot_calibration_{timestamp}.jsonl")
    parser.add_argument("--output-md", type=Path, default=root / "benchmark" / "reports" / f"pilot_calibration_{timestamp}.md")
    parser.add_argument("--top-rejected", type=int, default=3)
    parser.add_argument("--sample-chars", type=int, default=700)
    args = parser.parse_args()

    runs = read_jsonl(args.run)
    lookup = review_lookup(pd.read_parquet(args.data))
    rows = build_rows(runs, lookup, args.top_rejected, args.sample_chars)
    write_jsonl(args.output_jsonl, rows)
    write_markdown(args.output_md, rows, args.run)
    print(f"Wrote {len(rows)} calibration regions to {args.output_jsonl}")
    print(f"Wrote markdown sheet to {args.output_md}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
