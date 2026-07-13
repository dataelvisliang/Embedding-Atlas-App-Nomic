#!/usr/bin/env python3
"""Run a small Projection-Augmented Retrieval pilot.

This is a repeatable smoke-test runner, not the final benchmark harness. It
uses the frozen dev queries, the local Wine Atlas parquet, and OpenRouter to
exercise the agent loop:

    scan_regions -> inspect_regions -> optional refine_region -> stop/final

Outputs JSONL records compatible with the benchmark run schema plus pilot-only
fields such as accepted/rejected/frontier summaries and final_answer.
"""

from __future__ import annotations

import argparse
import json
import math
import os
import random
import re
import time
import urllib.error
import urllib.request
from dataclasses import dataclass, field
from datetime import datetime, timezone
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from typing import Any

import pandas as pd


DEFAULT_QUERY_IDS = ["wine-dev-005", "wine-dev-006", "wine-dev-010"]
OPENROUTER_URL = "https://openrouter.ai/api/v1/chat/completions"
PILOT_WALL_CLOCK_MS = 300_000
ANALYZER_JSON_SCHEMA = {"name": "wine_region_analysis", "strict": True, "schema": {"type": "object", "additionalProperties": False, "required": ["category", "sentiment", "themes", "quotes", "purity", "purity_rationale", "intent_match", "intent_match_rationale", "hard_constraint_match", "outlier_count"], "properties": {"category": {"type": "string"}, "sentiment": {"type": "string", "enum": ["Excellent", "Good", "Mediocre"]}, "themes": {"type": "array", "items": {"type": "string"}}, "quotes": {"type": "array", "items": {"type": "string"}}, "purity": {"type": "number", "minimum": 0, "maximum": 1}, "purity_rationale": {"type": "string"}, "intent_match": {"type": "number", "minimum": 0, "maximum": 1}, "intent_match_rationale": {"type": "string"}, "hard_constraint_match": {"type": "boolean"}, "outlier_count": {"type": "integer", "minimum": 0}}}}


TOOL_DEFINITIONS: list[dict[str, Any]] = [
    {
        "type": "function",
        "function": {
            "name": "search_reviews",
            "description": "Structured lexical and metadata retrieval. Use it for known flavor, grape, country, score, or price constraints; do not use it to explore unknown spatial themes.",
            "parameters": {
                "type": "object",
                "properties": {
                    "terms": {"type": "array", "items": {"type": "string"}},
                    "term_mode": {"type": "string", "enum": ["AND", "OR"]},
                    "countries": {"type": "array", "items": {"type": "string"}},
                    "varieties": {"type": "array", "items": {"type": "string"}},
                    "min_points": {"type": "number"},
                    "max_points": {"type": "number"},
                    "min_price": {"type": "number"},
                    "max_price": {"type": "number"},
                    "limit": {"type": "number"},
                },
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "scan_regions",
            "description": "Coarse global scan of the 2D projection. Returns densest grid cells as candidate regions with centers, suggested radii, density, and summary statistics.",
            "parameters": {
                "type": "object",
                "properties": {
                    "grid_size": {"type": "number"},
                    "top_k": {"type": "number"},
                    "countries": {"type": "array", "items": {"type": "string"}},
                    "varieties": {"type": "array", "items": {"type": "string"}},
                    "terms": {"type": "array", "items": {"type": "string"}},
                    "term_mode": {"type": "string", "enum": ["AND", "OR"]},
                    "min_points": {"type": "number"},
                    "max_points": {"type": "number"},
                    "min_price": {"type": "number"},
                    "max_price": {"type": "number"},
                },
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "inspect_regions",
            "description": "Place several circular probes in one call. Each circle is sampled and analyzed for density, themes, purity, intent_match, and projection agreement.",
            "parameters": {
                "type": "object",
                "properties": {
                    "regions": {
                        "type": "array",
                        "minItems": 1,
                        "maxItems": 8,
                        "items": {
                            "type": "object",
                            "properties": {
                                "id": {"type": "string"},
                                "center_x": {"type": "number"},
                                "center_y": {"type": "number"},
                                "radius": {"type": "number"},
                            },
                            "required": ["center_x", "center_y", "radius"],
                        },
                    },
                    "intent": {"type": "string"},
                    "resample_ids": {"type": "array", "items": {"type": "string"}},
                    "sample_size": {"type": "number"},
                },
                "required": ["regions", "intent"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "refine_region",
            "description": "Zoom into one promising circular region and propose smaller child regions for projection-guided purification.",
            "parameters": {
                "type": "object",
                "properties": {
                    "parent_id": {"type": "string"},
                    "center_x": {"type": "number"},
                    "center_y": {"type": "number"},
                    "radius": {"type": "number"},
                    "objective": {
                        "type": "string",
                        "enum": [
                            "maximize_purity",
                            "maximize_intent_match",
                            "find_distinct_subthemes",
                        ],
                    },
                    "subdivisions": {"type": "number"},
                    "top_k": {"type": "number"},
                },
                "required": ["parent_id", "center_x", "center_y", "radius"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "compare_regions",
            "description": "Compare two to six circular regions using consistent density, score, price, country, and variety summaries.",
            "parameters": {
                "type": "object",
                "properties": {
                    "regions": {
                        "type": "array",
                        "items": {
                            "type": "object",
                            "properties": {
                                "id": {"type": "string"},
                                "center_x": {"type": "number"},
                                "center_y": {"type": "number"},
                                "radius": {"type": "number"},
                            },
                            "required": ["id", "center_x", "center_y", "radius"],
                        },
                    }
                },
                "required": ["regions"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "save_results",
            "description": "Persist already verified review IDs under a category for UI cards.",
            "parameters": {
                "type": "object",
                "properties": {
                    "review_ids": {"type": "array", "items": {"type": "number"}},
                    "category": {"type": "string"},
                },
                "required": ["review_ids", "category"],
            },
        },
    },
]


ANALYZER_SYSTEM_PROMPT = """You are a specialized Wine Review Analyzer Agent.

Output only one JSON object with exactly these keys:
{
  "category": "...",
  "sentiment": "Excellent|Good|Mediocre",
  "themes": ["note1", "note2"],
  "quotes": ["quote1"],
  "purity": 0.0,
  "purity_rationale": "one evidence-based sentence",
  "intent_match": 0.0,
  "intent_match_rationale": "one evidence-based sentence",
  "hard_constraint_match": true,
  "outlier_count": 0
}

Purity measures whether sampled reviews share one coherent wine theme.
Intent match measures fit to the supplied user intent. If the sample is broad
or mixed, still choose the best category and lower the scores. Score supplied
reviews only; do not infer from coordinates or density. hard_constraint_match
must be false whenever a stated color, price, score, country, or variety
constraint is contradicted by the sampled evidence.
"""


def repo_root() -> Path:
    return Path(__file__).resolve().parents[2]


def load_env(path: Path) -> dict[str, str]:
    values: dict[str, str] = {}
    for line in path.read_text(encoding="utf-8").splitlines():
        if line.strip() and not line.lstrip().startswith("#") and "=" in line:
            key, value = line.split("=", 1)
            values[key.strip()] = value.strip()
    return values


def load_prompt(path: Path) -> str:
    text = path.read_text(encoding="utf-8")
    match = re.search(r"SPATIAL_SYSTEM_PROMPT\s*=\s*`([\s\S]+)`;", text)
    if not match:
        raise RuntimeError(f"Could not extract SPATIAL_SYSTEM_PROMPT from {path}")
    return match.group(1)


def load_queries(path: Path, query_ids: list[str]) -> list[dict[str, Any]]:
    wanted = set(query_ids)
    queries = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        item = json.loads(line)
        if item["query_id"] in wanted:
            queries.append(item)
    found = {q["query_id"] for q in queries}
    missing = [qid for qid in query_ids if qid not in found]
    if missing:
        raise RuntimeError(f"Missing query IDs: {', '.join(missing)}")
    order = {qid: index for index, qid in enumerate(query_ids)}
    return sorted(queries, key=lambda q: order[q["query_id"]])


class OpenRouterClient:
    def __init__(self, api_key: str, model: str, timeout: int = 120):
        self.api_key = api_key
        self.model = model
        self.timeout = timeout

    def chat(self, body: dict[str, Any], title: str) -> dict[str, Any]:
        payload = json.dumps(body).encode("utf-8")
        request = urllib.request.Request(
            OPENROUTER_URL,
            data=payload,
            method="POST",
            headers={
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json",
                "HTTP-Referer": "http://localhost:5173",
                "X-Title": title,
            },
        )
        try:
            with urllib.request.urlopen(request, timeout=self.timeout) as response:
                return json.loads(response.read().decode("utf-8"))
        except urllib.error.HTTPError as error:
            detail = error.read().decode("utf-8", "replace")
            raise RuntimeError(f"OpenRouter HTTP {error.code}: {detail[:1000]}") from error
        except urllib.error.URLError as error:
            raise RuntimeError(f"OpenRouter request failed after {self.timeout}s: {error.reason}") from error


def score_value(value: Any, fallback: float = 0.5) -> float:
    if isinstance(value, str):
        label = value.strip().lower()
        if label in {"none", "absent", "no", "very low"}:
            return 0.0
        if label in {"low", "weak"}:
            return 0.25
        if label in {"medium", "moderate", "mixed", "partial"}:
            return 0.5
        if label in {"high", "strong"}:
            return 0.75
        if label in {"very high", "excellent", "perfect"}:
            return 1.0
    try:
        number = float(value)
    except (TypeError, ValueError):
        return fallback
    if not math.isfinite(number):
        return fallback
    return round(min(1.0, max(0.0, number)), 3)


def parse_json_object(content: str) -> dict[str, Any] | None:
    try:
        parsed = json.loads(content)
    except json.JSONDecodeError:
        match = re.search(r"\{[\s\S]+\}", content or "")
        if not match:
            return None
        try:
            parsed = json.loads(match.group(0))
        except json.JSONDecodeError:
            return None
    if not isinstance(parsed, dict):
        return None
    return parsed


def normalize_analysis(parsed: dict[str, Any] | None) -> dict[str, Any] | None:
    if not parsed or not isinstance(parsed.get("category"), str):
        return None
    parsed.setdefault("themes", [])
    parsed.setdefault("quotes", [])
    parsed.setdefault("sentiment", "Good")
    if not isinstance(parsed["themes"], list):
        parsed["themes"] = []
    if not isinstance(parsed["quotes"], list):
        parsed["quotes"] = []
    purity = score_value(parsed.get("purity"), float("nan"))
    intent_match = score_value(parsed.get("intent_match"), float("nan"))
    if not math.isfinite(purity) or not math.isfinite(intent_match):
        return None
    parsed["purity"] = purity
    parsed["intent_match"] = intent_match
    parsed["hard_constraint_match"] = parsed.get("hard_constraint_match") if isinstance(parsed.get("hard_constraint_match"), bool) else None
    return parsed


class AtlasTools:
    def __init__(self, data_path: Path, client: OpenRouterClient, sample_size: int, seed: int):
        self.df = pd.read_parquet(data_path)
        self.client = client
        self.sample_size = sample_size
        self.seed = seed
        self.df["price_num"] = pd.to_numeric(self.df["price"], errors="coerce")
        self.df["points_num"] = pd.to_numeric(self.df["points"], errors="coerce")
        self.df["description_s"] = self.df["description"].fillna("").astype(str)
        self.df["country_s"] = self.df["country"].fillna("").astype(str)
        self.df["variety_s"] = self.df["variety"].fillna("").astype(str)

    def execute(self, call: dict[str, Any]) -> dict[str, Any]:
        name = call["function"]["name"]
        try:
            args = json.loads(call["function"].get("arguments") or "{}")
        except json.JSONDecodeError as exc:
            return {
                "name": name,
                "call_id": call["id"],
                "result": None,
                "error": f"invalid_tool_args: {exc.msg}",
            }
        if name == "search_reviews":
            return self.search_reviews(call["id"], args)
        if name == "scan_regions":
            return self.scan_regions(call["id"], args)
        if name == "inspect_regions":
            return self.inspect_regions(call["id"], args)
        if name == "refine_region":
            return self.refine_region(call["id"], args)
        if name == "compare_regions":
            return self.compare_regions(call["id"], args)
        if name == "save_results":
            return {
                "name": name,
                "call_id": call["id"],
                "result": {
                    "saved": True,
                    "count": len(args.get("review_ids", [])),
                    "category": args.get("category"),
                    "review_ids": args.get("review_ids", []),
                },
            }
        return {"name": name, "call_id": call["id"], "result": None, "error": "unknown tool"}

    def filter_mask(self, args: dict[str, Any]) -> pd.Series:
        context = args.get("search_context") if isinstance(args.get("search_context"), dict) else {}
        hard_filters = context.get("hard_filters") if isinstance(context.get("hard_filters"), dict) else {}
        args = {**args, **hard_filters}
        mask = pd.Series(True, index=self.df.index)
        terms = [str(term).strip().lower() for term in args.get("terms", []) if str(term).strip()][:10]
        if terms:
            term_mask = pd.Series(args.get("term_mode") != "OR", index=self.df.index)
            for term in terms:
                item = self.df["description_s"].str.lower().str.contains(re.escape(term), regex=True, na=False)
                term_mask = term_mask | item if args.get("term_mode") == "OR" else term_mask & item
            mask &= term_mask
        if args.get("countries"):
            mask &= self.df["country_s"].isin([str(value) for value in args["countries"]])
        if args.get("varieties"):
            mask &= self.df["variety_s"].isin([str(value) for value in args["varieties"]])
        comparisons = [
            ("min_points", "points_num", "ge"),
            ("max_points", "points_num", "le"),
            ("min_price", "price_num", "ge"),
            ("max_price", "price_num", "le"),
        ]
        for key, column, op in comparisons:
            if key in args and args[key] is not None:
                value = float(args[key])
                mask &= self.df[column] >= value if op == "ge" else self.df[column] <= value
        return mask.fillna(False)

    def circle_mask(self, region: dict[str, Any], frame: pd.DataFrame | None = None) -> pd.Series:
        source = self.df if frame is None else frame
        x = float(region["center_x"])
        y = float(region["center_y"])
        radius = max(float(region["radius"]), 0.0001)
        return ((source["projection_x"] - x) ** 2 + (source["projection_y"] - y) ** 2) <= radius * radius

    def search_reviews(self, call_id: str, args: dict[str, Any]) -> dict[str, Any]:
        limit = int(max(1, min(50, float(args.get("limit", 15)))))
        filtered = self.df[self.filter_mask(args)].sort_values("points_num", ascending=False).head(limit)
        reviews = [self.review_from_row(row) for _, row in filtered.iterrows()]
        return {
            "name": "search_reviews",
            "call_id": call_id,
            "result": {
                "total_matches": int(self.filter_mask(args).sum()),
                "matches_returned": len(reviews),
                "reviews": reviews,
            },
        }

    def scan_regions(self, call_id: str, args: dict[str, Any]) -> dict[str, Any]:
        grid = max(0.05, min(1000.0, float(args.get("grid_size", 1))))
        top_k = int(max(1, min(30, float(args.get("top_k", 12)))))
        filtered = self.df[self.filter_mask(args)].copy()
        if filtered.empty:
            regions: list[dict[str, Any]] = []
        else:
            filtered["bin_x"] = (filtered["projection_x"] / grid).apply(math.floor)
            filtered["bin_y"] = (filtered["projection_y"] / grid).apply(math.floor)
            grouped = (
                filtered.groupby(["bin_x", "bin_y"])
                .agg(
                    density=("__row_index__", "count"),
                    avg_points=("points_num", "mean"),
                    avg_price=("price_num", "mean"),
                )
                .reset_index()
                .sort_values("density", ascending=False)
                .head(top_k)
            )
            regions = []
            for index, row in enumerate(grouped.itertuples(index=False), 1):
                regions.append(
                    {
                        "id": f"scan-{index}",
                        "center_x": round((row.bin_x + 0.5) * grid, 4),
                        "center_y": round((row.bin_y + 0.5) * grid, 4),
                        "suggested_radius": round(grid * math.sqrt(0.5), 4),
                        "grid_size": grid,
                        "density": int(row.density),
                        "avg_points": None if pd.isna(row.avg_points) else round(float(row.avg_points), 1),
                        "avg_price": None if pd.isna(row.avg_price) else round(float(row.avg_price), 2),
                    }
                )
        return {"name": "scan_regions", "call_id": call_id, "result": {"strategy": "coarse_grid_scan", "regions": regions}}

    def inspect_regions(self, call_id: str, args: dict[str, Any]) -> dict[str, Any]:
        regions = list(args.get("regions") or [])[:8]
        intent = str(args.get("intent") or "Open-ended discovery")[:500]
        sample_size = int(max(3, min(self.sample_size, float(args.get("sample_size", self.sample_size)))))

        def inspect_one(index_region: tuple[int, dict[str, Any]]) -> dict[str, Any]:
            index, region = index_region
            probe = {
                "id": region.get("id") or f"probe-{index + 1}",
                "center_x": float(region["center_x"]),
                "center_y": float(region["center_y"]),
                "radius": float(region.get("radius") or region.get("suggested_radius") or 1),
            }
            try:
                subset = self.df[self.circle_mask(probe) & self.filter_mask(args)]
                density = len(subset)
                sample = subset.sample(n=min(sample_size, density), random_state=self.seed + index) if density else subset
                reviews = [self.review_from_row(row) for _, row in sample.iterrows()]
                analysis = self.analyze(probe, intent, reviews)
            except Exception as exc:
                density = 0
                sample = self.df.iloc[0:0]
                reviews = []
                analysis = {
                    "category": "Analysis failed",
                    "sentiment": "N/A",
                    "themes": [],
                    "quotes": [],
                    "purity": 0,
                    "purity_rationale": f"Analyzer/tool exception: {type(exc).__name__}",
                    "intent_match": 0,
                    "intent_match_rationale": "This region could not be analyzed safely.",
                    "outlier_count": 0,
                    "analysis_failed": True,
                    "analyzer_usage": {"total_tokens": 0},
                }
            analysis.update(probe)
            analysis.update(
                {
                    "intent": intent,
                    "density": int(density),
                    "sample_size": len(reviews),
                    "projection_agreement": self.projection_agreement(sample, probe),
                    "review_ids": [review["id"] for review in reviews],
                    "reviews": reviews,
                }
            )
            return analysis

        with ThreadPoolExecutor(max_workers=max(1, min(8, len(regions)))) as executor:
            analyses = list(executor.map(inspect_one, enumerate(regions)))
        return {
            "name": "inspect_regions",
            "call_id": call_id,
            "result": {"strategy": "parallel_circular_probes", "intent": intent, "regions": analyses},
        }

    def refine_region(self, call_id: str, args: dict[str, Any]) -> dict[str, Any]:
        parent = {
            "center_x": float(args["center_x"]),
            "center_y": float(args["center_y"]),
            "radius": float(args["radius"]),
        }
        objective = args.get("objective", "maximize_purity")
        subdivisions = int(max(2, min(10, float(args.get("subdivisions", 4)))))
        top_k = int(max(1, min(12, float(args.get("top_k", 6)))))
        cell = parent["radius"] * 2 / subdivisions
        origin_x = parent["center_x"] - parent["radius"]
        origin_y = parent["center_y"] - parent["radius"]
        subset = self.df[self.circle_mask(parent) & self.filter_mask(args)].copy()
        children = []
        if not subset.empty:
            subset["cell_x"] = ((subset["projection_x"] - origin_x) / cell).apply(math.floor)
            subset["cell_y"] = ((subset["projection_y"] - origin_y) / cell).apply(math.floor)
            grouped = (
                subset.groupby(["cell_x", "cell_y"])
                .agg(
                    density=("__row_index__", "count"),
                    avg_points=("points_num", "mean"),
                    avg_price=("price_num", "mean"),
                    variety_count=("variety_s", "nunique"),
                    country_count=("country_s", "nunique"),
                )
                .reset_index()
                .sort_values("density", ascending=False)
                .head(top_k)
            )
            for index, row in enumerate(grouped.itertuples(index=False), 1):
                child = {
                    "id": f"{args.get('parent_id', 'refined')}-{index}",
                    "center_x": round(origin_x + (row.cell_x + 0.5) * cell, 4),
                    "center_y": round(origin_y + (row.cell_y + 0.5) * cell, 4),
                    "radius": round(cell * math.sqrt(0.5), 4),
                    "suggested_radius": round(cell * math.sqrt(0.5), 4),
                    "objective": objective,
                    "density": int(row.density),
                    "avg_points": None if pd.isna(row.avg_points) else round(float(row.avg_points), 1),
                    "avg_price": None if pd.isna(row.avg_price) else round(float(row.avg_price), 2),
                    "variety_count": int(row.variety_count),
                    "country_count": int(row.country_count),
                }
                children.append(child)
        return {
            "name": "refine_region",
            "call_id": call_id,
            "result": {"parent": parent, "objective": objective, "strategy": "projection_guided_purification", "children": children},
        }

    def compare_regions(self, call_id: str, args: dict[str, Any]) -> dict[str, Any]:
        comparisons = []
        for region in list(args.get("regions") or [])[:6]:
            probe = {
                "id": region.get("id"),
                "center_x": float(region["center_x"]),
                "center_y": float(region["center_y"]),
                "radius": float(region["radius"]),
            }
            subset = self.df[self.circle_mask(probe) & self.filter_mask(args)]
            comparisons.append(
                {
                    **probe,
                    "density": int(len(subset)),
                    "avg_points": None if subset.empty else round(float(subset["points_num"].mean()), 1),
                    "avg_price": None if subset.empty else round(float(subset["price_num"].mean()), 2),
                }
            )
        return {"name": "compare_regions", "call_id": call_id, "result": {"regions": comparisons}}

    def analyze(self, region: dict[str, Any], intent: str, reviews: list[dict[str, Any]]) -> dict[str, Any]:
        if not reviews:
            return {
                "category": "Empty region",
                "sentiment": "N/A",
                "themes": [],
                "quotes": [],
                "purity": 0,
                "purity_rationale": "No sampled reviews.",
                "intent_match": 0,
                "intent_match_rationale": "No evidence.",
                "hard_constraint_match": False,
                "outlier_count": 0,
                "analyzer_usage": {"total_tokens": 0},
            }
        reviews_text = "\n\n".join(
            [
                f"[{index + 1}] Points: {review.get('points')} | Price: {review.get('price')} | Variety: {review.get('variety')} | Country: {review.get('country')}\nTitle: {review.get('title')}\n{review.get('text')}"
                for index, review in enumerate(reviews)
            ]
        )
        usage: dict[str, Any] = {"total_tokens": 0}
        failure_reasons: list[str] = []
        for attempt in range(3):
            retry = attempt > 0
            try:
                data = self.client.chat(
                {
                    "model": self.client.model,
                    "messages": [
                        {"role": "system", "content": ANALYZER_SYSTEM_PROMPT},
                        {
                            "role": "user",
                            "content": (
                                "Retry: return only the required JSON object. Do not add explanations.\n\n"
                                if retry
                                else ""
                            )
                            + f"User intent: {intent}\n\nAnalyze these {len(reviews)} sampled reviews. If evidence is broad or mixed, return lower purity/intent_match rather than failing. hard_constraint_match must be false if any explicit user requirement (such as wine color, price, country, variety, or score) is contradicted by the sample; otherwise true.\n\n{reviews_text}",
                        },
                    ],
                    "temperature": 0,
                    "max_tokens": 900,
                    "response_format": {"type": "json_schema", "json_schema": ANALYZER_JSON_SCHEMA},
                    "reasoning": {"effort": "none", "exclude": True},
                    "plugins": [{"id": "response-healing"}],
                },
                "Wine Atlas Analyzer pilot",
                )
            except Exception as exc:
                failure_reasons.append(f"request_error:{type(exc).__name__}")
                continue
            usage = data.get("usage", {})
            content = data.get("choices", [{}])[0].get("message", {}).get("content") or ""
            if not content.strip():
                failure_reasons.append("empty_content")
                continue
            raw = parse_json_object(content)
            if raw is None:
                failure_reasons.append("invalid_json")
                continue
            parsed = normalize_analysis(raw)
            if parsed is None:
                failure_reasons.append("schema_invalid")
                continue
            if parsed:
                parsed["outlier_count"] = int(max(0, min(len(reviews), round(float(parsed.get("outlier_count", 0) or 0)))))
                parsed["analyzer_usage"] = usage
                parsed["analyzer_status"] = "ok"
                parsed["analyzer_attempts"] = attempt + 1
                return parsed
        return {
            "category": "Analysis failed",
            "sentiment": "N/A",
            "themes": [],
            "quotes": [],
            "purity": 0,
            "purity_rationale": "Analyzer failed after recovery attempts: " + ", ".join(failure_reasons[-3:]),
            "intent_match": 0,
            "intent_match_rationale": "Analyzer did not return valid structured evidence after retry.",
            "hard_constraint_match": False,
            "outlier_count": len(reviews),
            "analysis_failed": True,
            "analyzer_status": failure_reasons[-1] if failure_reasons else "unknown_failure",
            "analyzer_attempts": 3,
            "analyzer_usage": usage,
        }

    def projection_agreement(self, sample: pd.DataFrame, region: dict[str, Any]) -> float | None:
        ids: set[int] = set()
        for _, row in sample.iterrows():
            neighbors = row.get("neighbors")
            try:
                neighbor_ids = neighbors.get("ids") if hasattr(neighbors, "get") else None
                for value in list(neighbor_ids)[1:11]:
                    ids.add(int(value))
            except Exception:
                continue
        if not ids:
            return None
        subset = self.df[self.df["__row_index__"].isin(list(ids)[:300])]
        if subset.empty:
            return None
        return round(float(self.circle_mask(region, subset).sum()) / len(subset), 3)

    @staticmethod
    def review_from_row(row: pd.Series) -> dict[str, Any]:
        return {
            "id": int(row["__row_index__"]),
            "points": None if pd.isna(row.get("points")) else int(row.get("points")),
            "title": str(row.get("title") or ""),
            "price": None if pd.isna(row.get("price")) else float(row.get("price")),
            "variety": str(row.get("variety") or ""),
            "country": str(row.get("country") or ""),
            "text": str(row.get("description") or ""),
            "projection_x": float(row["projection_x"]),
            "projection_y": float(row["projection_y"]),
        }


def as_region(value: Any) -> dict[str, Any] | None:
    if not isinstance(value, dict):
        return None
    try:
        center_x = float(value["center_x"])
        center_y = float(value["center_y"])
        radius = float(value.get("radius") or value.get("suggested_radius"))
    except (KeyError, TypeError, ValueError):
        return None
    if not all(math.isfinite(v) for v in [center_x, center_y, radius]) or radius <= 0:
        return None
    return {"id": value.get("id"), "center_x": center_x, "center_y": center_y, "radius": radius}


def nearly_same_circle(a: dict[str, Any], b: dict[str, Any]) -> bool:
    distance = math.hypot(float(a["center_x"]) - float(b["center_x"]), float(a["center_y"]) - float(b["center_y"]))
    scale = max(min(float(a["radius"]), float(b["radius"])), 1e-9)
    return distance <= scale * 0.25 and max(float(a["radius"]), float(b["radius"])) / scale <= 1.25


@dataclass
class Candidate:
    id: str
    center_x: float
    center_y: float
    radius: float
    category: str
    themes: list[str]
    purity: float
    intent_match: float
    projection_agreement: float | None
    utility: float
    recommended_action: str
    acceptance_tier: str | None
    hard_constraint_match: bool
    sample_size: int
    review_ids: list[int]
    parent_id: str | None = None
    refine_depth: int = 0
    analysis_failed: bool = False


@dataclass
class PilotPolicy:
    target_count: int
    exploration: bool = False
    has_hard_constraints: bool = False
    hard_constraint_text: str = ""
    structured_filters: dict[str, float] = field(default_factory=dict)
    started_at: float = field(default_factory=time.time)
    tool_calls: int = 0
    scans: int = 0
    searches: int = 0
    inspected_regions: int = 0
    refinements: int = 0
    comparisons: int = 0
    saved_categories: int = 0
    model_tokens: int = 0
    model_cost: float = 0.0
    visited_regions: list[dict[str, Any]] = field(default_factory=list)
    candidates: dict[str, Candidate] = field(default_factory=dict)
    authorized_regions: dict[str, dict[str, Any]] = field(default_factory=dict)
    events: list[dict[str, Any]] = field(default_factory=list)
    discovered_themes: set[str] = field(default_factory=set)
    relevant_themes: set[str] = field(default_factory=set)
    no_progress_rounds: int = 0
    stop_reason: str | None = None
    save_signatures: set[str] = field(default_factory=set)
    saved_after_stop: bool = False

    def snapshot(self) -> dict[str, Any]:
        elapsed_ms = int((time.time() - self.started_at) * 1000)
        if elapsed_ms >= PILOT_WALL_CLOCK_MS and not self.stop_reason:
            self.stop_reason = f"wall-clock budget {PILOT_WALL_CLOCK_MS}ms exhausted"
        if self.model_tokens >= 80_000 and not self.stop_reason:
            self.stop_reason = "model-token budget 80000 exhausted"
        candidates = sorted([candidate.__dict__ for candidate in self.candidates.values()], key=lambda item: item["utility"], reverse=True)
        frontier = [item for item in candidates if item["recommended_action"] in {"refine", "resample", "compare", "explore"} and item["utility"] >= 0.40]
        return {
            "must_stop": bool(self.stop_reason),
            "stop_reason": self.stop_reason,
            "objective": {"target_accepted_regions": self.target_count, "requires_comparison": False, "exploration": self.exploration, "has_hard_constraints": self.has_hard_constraints, "structured_filters": self.structured_filters},
            "remaining": {
                "toolCalls": max(0, 18 - self.tool_calls),
                "scans": max(0, 2 - self.scans),
                "searches": max(0, 4 - self.searches),
                "inspectedRegions": max(0, 24 - self.inspected_regions),
                "refinements": max(0, 5 - self.refinements),
                "comparisons": max(0, 4 - self.comparisons),
                "savedCategories": max(0, 8 - self.saved_categories),
                "modelTokens": max(0, 80_000 - self.model_tokens),
            },
            "inspected_region_count": len(self.visited_regions),
            "accepted_region_count": len([item for item in candidates if item["recommended_action"] == "accept"]),
            "discovered_themes": list(self.discovered_themes)[-30:],
            "relevant_themes": list(self.relevant_themes)[-30:],
            "no_progress_rounds": self.no_progress_rounds,
            "elapsed_ms": elapsed_ms,
            "frontier": frontier,
            "candidates": candidates,
            "recent_events": self.events[-8:],
            "trajectory": self.events,
        }

    def record_usage(self, usage: dict[str, Any] | None) -> None:
        if not usage:
            return
        self.model_tokens += int(usage.get("total_tokens") or 0)
        self.model_cost += float(usage.get("cost") or 0)

    def evaluate(self, call: dict[str, Any]) -> tuple[dict[str, Any] | None, dict[str, Any] | None]:
        name = call["function"]["name"]
        try:
            args = json.loads(call["function"].get("arguments") or "{}")
        except json.JSONDecodeError as exc:
            return None, self.block(call, f"invalid_tool_args: {exc.msg}")
        if self.stop_reason and name != "save_results":
            return None, self.block(call, f"Search stopped: {self.stop_reason}")
        if self.tool_calls >= 18 and name != "save_results":
            self.stop_reason = "tool-call budget 18 exhausted"
            return None, self.block(call, self.stop_reason)
        if name == "scan_regions":
            if self.scans >= 2:
                return None, self.block(call, "scan budget exhausted")
            self.scans += 1
            return self.accept(self.inject_structured_filters(call, args)), None
        if name == "search_reviews":
            if self.searches >= 4:
                return None, self.block(call, "structured-search budget exhausted")
            self.searches += 1
            return self.accept(self.inject_structured_filters(call, args)), None
        if name == "inspect_regions":
            call = self.inject_structured_filters(call, args)
            args = json.loads(call["function"].get("arguments") or "{}")
            requested = [region for region in [as_region(item) for item in args.get("regions", [])] if region]
            unique = []
            for region in requested:
                region_id = str(region.get("id") or "")
                authorized = self.authorized_regions.get(region_id)
                can_resample = bool(region_id and region_id in args.get("resample_ids", []) and self.candidates.get(region_id, None) and self.candidates[region_id].recommended_action == "resample")
                if self.authorized_regions and not authorized and not can_resample:
                    continue
                if authorized and not nearly_same_circle(authorized, region):
                    continue
                duplicate = any(nearly_same_circle(previous, region) for previous in self.visited_regions + unique)
                if not duplicate:
                    unique.append(region)
            if not unique:
                return None, self.block(call, "every probe must use an authorized scan/refine/resample candidate ID and exact geometry")
            accepted = unique[: max(0, 24 - self.inspected_regions)]
            args["regions"] = accepted
            rewritten = {**call, "function": {**call["function"], "arguments": json.dumps(args)}}
            self.visited_regions.extend(accepted)
            self.inspected_regions += len(accepted)
            self.tool_calls += 1
            self.events.append({"tool": name, "status": "accepted" if len(accepted) == len(requested) else "filtered", "detail": f"{len(accepted)}/{len(requested)} unique probes", "parameters": args})
            return rewritten, None
        if name == "refine_region":
            call = self.inject_structured_filters(call, args)
            args = json.loads(call["function"].get("arguments") or "{}")
            parent_id = str(args.get("parent_id") or "")
            parent = self.candidates.get(parent_id)
            if not parent:
                return None, self.block(call, "refine_region requires parent_id from an inspected candidate")
            if parent.refine_depth >= 1:
                return None, self.block(call, f"candidate {parent_id} already reached refine depth 1")
            if parent.recommended_action not in {"refine", "explore"}:
                return None, self.block(call, f"candidate {parent_id} is {parent.recommended_action}, not a refinement branch")
            self.refinements += 1
            return self.accept(call), None
        if name == "compare_regions":
            call = self.inject_structured_filters(call, args)
            self.comparisons += 1
            return self.accept(call), None
        if name == "save_results":
            save_decision = self.evaluate_save(call, args)
            return (save_decision, None) if "function" in save_decision else (None, save_decision)
        return self.accept(call), None

    def evaluate_save(self, call: dict[str, Any], args: dict[str, Any]) -> dict[str, Any] | None:
        requested_ids = [int(value) for value in args.get("review_ids", []) if isinstance(value, (int, float)) or str(value).isdigit()]
        category = str(args.get("category") or "").strip().lower()
        save_key = json.dumps({"category": category, "review_ids": sorted(set(requested_ids))}, sort_keys=True)
        if self.stop_reason and self.saved_after_stop:
            return self.block(call, "search is already stopped and final save has already been attempted; answer now without more tools")
        if save_key in self.save_signatures:
            return self.block(call, "duplicate save_results request; answer now without more tools")
        self.save_signatures.add(save_key)
        self.saved_categories += 1
        if self.stop_reason:
            self.saved_after_stop = True
        self.events.append({"tool": "save_results", "status": "accepted", "parameters": args})
        return call

    def accept(self, call: dict[str, Any]) -> dict[str, Any]:
        self.tool_calls += 1
        self.events.append({"tool": call["function"]["name"], "status": "accepted", "parameters": json.loads(call["function"].get("arguments") or "{}")})
        return call

    def inject_structured_filters(self, call: dict[str, Any], args: dict[str, Any]) -> dict[str, Any]:
        accepted = [candidate.id for candidate in self.candidates.values() if candidate.recommended_action == "accept"]
        frontier = [candidate.id for candidate in self.candidates.values() if candidate.recommended_action in {"refine", "resample", "compare", "explore"}]
        context = {
            "version": 1,
            "hard_filters": self.structured_filters,
            "semantic_intent": self.hard_constraint_text,
            "projection_state": {"visited_region_ids": [str(region.get("id")) for region in self.visited_regions if region.get("id")]},
            "evidence_state": {"accepted_region_ids": accepted, "frontier_region_ids": frontier},
        }
        injected = {**args, "search_context": context}
        for key, value in self.structured_filters.items():
            injected.setdefault(key, value)
        if args.get("search_context") == context:
            return call
        return {**call, "function": {**call["function"], "arguments": json.dumps(injected)}}

    def block(self, call: dict[str, Any], reason: str) -> dict[str, Any]:
        self.events.append({"tool": call["function"]["name"], "status": "blocked", "detail": reason})
        return {
            "name": call["function"]["name"],
            "call_id": call["id"],
            "result": {
                "policy_blocked": True,
                "reason": reason,
                "instruction": "Do not call more tools. Provide the final answer now, using verified findings and noting any missing target count." if self.stop_reason else "Follow SEARCH_POLICY_STATE.",
                "policy": self.snapshot(),
            },
        }

    def record_result(self, result: dict[str, Any]) -> None:
        if result.get("error"):
            self.events.append({"tool": result["name"], "status": "failed", "detail": result["error"]})
            return
        if result["name"] == "scan_regions":
            for item in result.get("result", {}).get("regions", []):
                region = as_region(item)
                if region and region.get("id"):
                    self.authorized_regions[str(region["id"])] = {**region, "source": "scan"}
            self.events.append({"tool": result["name"], "status": "completed"})
            return
        if result["name"] == "refine_region":
            for item in result.get("result", {}).get("children", []):
                region = as_region(item)
                if region and region.get("id"):
                    self.authorized_regions[str(region["id"])] = {**region, "source": "refine"}
            self.events.append({"tool": result["name"], "status": "completed"})
            return
        if result["name"] != "inspect_regions":
            self.events.append({"tool": result["name"], "status": "completed"})
            return
        before_themes = set(self.discovered_themes)
        before_relevant = set(self.relevant_themes)
        new_relevant = 0
        promising = False
        for region in result["result"].get("regions", []):
            self.record_usage(region.get("analyzer_usage"))
            analysis_failed = bool(region.get("analysis_failed"))
            themes = sorted({str(item).strip().lower() for item in (region.get("themes") or []) + [region.get("category", "")] if str(item).strip()})
            self.discovered_themes.update(themes)
            purity = 0.0 if analysis_failed else score_value(region.get("purity"), 0.0)
            intent_match = 0.0 if analysis_failed else score_value(region.get("intent_match"), 0.0)
            novelty = len([theme for theme in themes if theme not in before_themes]) / len(themes) if themes else 0
            hard_constraint_match = (
                not self.has_hard_constraints
                or (region.get("hard_constraint_match") is not False and not violates_obvious_constraint(self.hard_constraint_text, themes))
            )
            acceptance_tier = None if analysis_failed or not hard_constraint_match else self.acceptance_tier(intent_match, purity, themes)
            coverage = len([theme for theme in themes if (intent_match >= 0.75 or acceptance_tier) and theme not in before_relevant]) / len(themes) if themes else 0
            agreement = region.get("projection_agreement")
            projection_confidence = 0.5 + 0.5 * score_value(agreement, 0.5) if isinstance(agreement, (int, float)) else 0.75
            confidence = min(1.0, float(region.get("sample_size") or 0) / 12) * projection_confidence
            effective_intent = max(intent_match, 0.75) if acceptance_tier else intent_match
            utility = 0.0 if analysis_failed else max(0.0, min(1.0, 0.45 * effective_intent + 0.20 * purity + 0.15 * novelty + 0.10 * coverage + 0.10 * confidence - 0.05))
            if analysis_failed or not hard_constraint_match or intent_match < 0.60:
                action = "reject"
            elif acceptance_tier:
                action = "accept"
            elif intent_match >= 0.75:
                action = "accept" if purity >= 0.70 else "refine"
            else:
                action = "resample" if purity >= 0.70 else "explore"
            if action == "accept":
                before_count = len(self.relevant_themes)
                self.relevant_themes.update(themes)
                new_relevant += len(self.relevant_themes) - before_count
            if intent_match >= 0.60 and not analysis_failed:
                promising = True
            region_id = region.get("id") or f"probe-{len(self.candidates) + 1}"
            parent_id = self.find_parent(region_id)
            parent = self.candidates.get(parent_id) if parent_id else None
            self.candidates[region_id] = Candidate(
                id=region_id,
                center_x=float(region["center_x"]),
                center_y=float(region["center_y"]),
                radius=float(region["radius"]),
                category=str(region.get("category") or "Unknown"),
                themes=themes,
                purity=round(purity, 3),
                intent_match=round(intent_match, 3),
                projection_agreement=agreement if isinstance(agreement, (int, float)) else None,
                utility=round(utility, 3),
                recommended_action=action,
                acceptance_tier=acceptance_tier,
                hard_constraint_match=hard_constraint_match,
                sample_size=int(region.get("sample_size") or 0),
                review_ids=[int(value) for value in region.get("review_ids", [])],
                parent_id=parent_id,
                refine_depth=(parent.refine_depth + 1 if parent else 0),
                analysis_failed=analysis_failed,
            )
        self.no_progress_rounds = 0 if new_relevant or promising else self.no_progress_rounds + 1
        self.events.append({"tool": "inspect_regions", "status": "completed", "detail": f"{len(result['result'].get('regions', []))} probes; {new_relevant} new relevant themes"})
        self.evaluate_stop()

    def acceptance_tier(self, intent_match: float, purity: float, themes: list[str]) -> str | None:
        if purity >= 0.70 and intent_match >= 0.75:
            return "strong"
        if purity >= 0.75 and intent_match >= 0.65:
            return "soft"
        if self.exploration and purity >= 0.70 and intent_match >= 0.60 and self.has_distinct_accepted_theme(themes):
            return "diversity"
        return None

    def has_distinct_accepted_theme(self, themes: list[str]) -> bool:
        normalized = {theme.strip().lower() for theme in themes if theme.strip()}
        if not normalized:
            return False
        accepted_themes = {
            theme.strip().lower()
            for candidate in self.candidates.values()
            if candidate.recommended_action == "accept"
            for theme in candidate.themes
        }
        return any(theme not in accepted_themes for theme in normalized)

    def evaluate_stop(self) -> None:
        if self.stop_reason:
            return
        candidates = list(self.candidates.values())
        accepted = [candidate for candidate in candidates if candidate.recommended_action == "accept"]
        frontier = [candidate for candidate in candidates if candidate.recommended_action in {"refine", "resample", "compare", "explore"} and candidate.utility >= 0.40]
        strong_frontier = [candidate for candidate in frontier if candidate.purity >= 0.70 and candidate.intent_match >= 0.65 and candidate.utility >= 0.50]
        best_frontier = max([candidate.utility for candidate in frontier], default=0)
        best_accepted = max([candidate.utility for candidate in accepted], default=0)
        if len(accepted) >= self.target_count and len(self.relevant_themes) >= min(2, self.target_count):
            self.stop_reason = f"semantic evidence target satisfied: {len(accepted)} accepted regions and {len(self.relevant_themes)} relevant themes"
        elif len(accepted) >= max(1, self.target_count - 1) and len(self.relevant_themes) >= min(2, self.target_count) and (best_frontier == 0 or best_frontier < best_accepted * 0.65):
            self.stop_reason = f"diminishing returns: {len(accepted)} accepted regions and no high-utility frontier remain"
        elif len(accepted) + len(strong_frontier) >= self.target_count and len(self.relevant_themes) + len(strong_frontier) >= min(2, self.target_count):
            self.stop_reason = f"frontier evidence is sufficient to finalize: {len(accepted)} accepted and {len(strong_frontier)} strong frontier candidates"
        elif self.no_progress_rounds >= 2 and (accepted or not strong_frontier):
            self.stop_reason = "2 consecutive probe rounds found no new relevant themes"
        elif frontier and best_frontier < 0.45:
            self.stop_reason = "best remaining candidate utility is below 0.45"

    def find_parent(self, candidate_id: str) -> str | None:
        matches = [item for item in self.candidates if candidate_id.startswith(f"{item}-")]
        return sorted(matches, key=len, reverse=True)[0] if matches else None


def compact_tool_result(result: dict[str, Any], policy: PilotPolicy) -> dict[str, Any]:
    item: dict[str, Any] = {"tool": result["name"]}
    if result["name"] == "scan_regions":
        item["regions_returned"] = len(result["result"].get("regions", []))
        item["top_regions"] = result["result"].get("regions", [])[:3]
    elif result["name"] == "inspect_regions":
        item["regions"] = [
            {
                "id": region.get("id"),
                "density": region.get("density"),
                "category": region.get("category"),
                "purity": region.get("purity"),
                "intent_match": region.get("intent_match"),
                "projection_agreement": region.get("projection_agreement"),
                "analysis_failed": bool(region.get("analysis_failed")),
                "analyzer_status": region.get("analyzer_status"),
                "analyzer_attempts": region.get("analyzer_attempts"),
                "purity_rationale": region.get("purity_rationale"),
                "action": policy.candidates.get(region.get("id")).recommended_action if region.get("id") in policy.candidates else None,
            }
            for region in result["result"].get("regions", [])
        ]
    elif result["name"] == "refine_region":
        item["objective"] = result["result"].get("objective")
        item["children_returned"] = len(result["result"].get("children", []))
        item["children"] = result["result"].get("children", [])[:4]
    elif result["name"] == "save_results":
        item["saved"] = result["result"]
    if result.get("error"):
        item["error"] = result["error"]
    return item


def tool_content_for_model(result: dict[str, Any], policy: PilotPolicy) -> dict[str, Any]:
    """Compact tool observation sent back to the agent.

    Full tool evidence is retained in the JSONL pilot record. The model only
    needs the policy-relevant facts for the next decision; sending full sampled
    reviews back through the loop makes pilot costs explode.
    """
    if result.get("result", {}).get("policy_blocked"):
        return result["result"]
    if result["name"] == "scan_regions":
        return {
            "strategy": result["result"].get("strategy"),
            "regions": result["result"].get("regions", []),
        }
    if result["name"] == "inspect_regions":
        regions = []
        for region in result["result"].get("regions", []):
            candidate = policy.candidates.get(region.get("id"))
            regions.append(
                {
                    "id": region.get("id"),
                    "center_x": region.get("center_x"),
                    "center_y": region.get("center_y"),
                    "radius": region.get("radius"),
                    "density": region.get("density"),
                    "category": region.get("category"),
                    "themes": region.get("themes", []),
                    "purity": region.get("purity"),
                    "purity_rationale": region.get("purity_rationale"),
                    "intent_match": region.get("intent_match"),
                    "intent_match_rationale": region.get("intent_match_rationale"),
                    "projection_agreement": region.get("projection_agreement"),
                    "outlier_count": region.get("outlier_count"),
                    "analysis_failed": bool(region.get("analysis_failed")),
                    "recommended_action": candidate.recommended_action if candidate else None,
                    "utility": candidate.utility if candidate else None,
                    "review_ids": region.get("review_ids", []),
                }
            )
        return {
            "strategy": result["result"].get("strategy"),
            "intent": result["result"].get("intent"),
            "regions": regions,
        }
    if result["name"] == "refine_region":
        return result["result"]
    if result["name"] == "compare_regions":
        return result["result"]
    if result["name"] == "search_reviews":
        payload = result["result"]
        return {
            "total_matches": payload.get("total_matches"),
            "matches_returned": payload.get("matches_returned"),
            "reviews": [
                {
                    "id": review.get("id"),
                    "points": review.get("points"),
                    "title": review.get("title"),
                    "price": review.get("price"),
                    "variety": review.get("variety"),
                    "country": review.get("country"),
                    "excerpt": (review.get("text") or "")[:240],
                }
                for review in payload.get("reviews", [])[:20]
            ],
        }
    return result.get("result")


def force_final_answer(client: OpenRouterClient, prompt: str, messages: list[dict[str, Any]], policy: PilotPolicy) -> str:
    data = client.chat(
        {
            "model": client.model,
            "messages": [
                {"role": "system", "content": prompt},
                *messages,
                {
                    "role": "system",
                    "content": "FINAL_ONLY: Do not call tools. Provide the final answer from verified findings. If fewer findings than requested were verified, say so briefly.",
                },
            ],
            "temperature": 0,
            "max_tokens": 900,
            "reasoning": {"effort": "none", "exclude": True},
        },
        "Wine Atlas Agent final pilot",
    )
    policy.record_usage(data.get("usage"))
    return data.get("choices", [{}])[0].get("message", {}).get("content") or ""


def fallback_final_answer(policy: PilotPolicy) -> str:
    candidates = sorted(policy.candidates.values(), key=lambda candidate: candidate.utility, reverse=True)
    selected = [candidate for candidate in candidates if candidate.recommended_action == "accept"]
    if not selected:
        selected = [
            candidate for candidate in candidates
            if candidate.hard_constraint_match and candidate.purity >= 0.70 and candidate.intent_match >= 0.65
        ][: policy.target_count]
    if not selected:
        return "I could not verify a sufficiently relevant region within the available search budget."
    findings = "; ".join(
        f"{candidate.category} (purity {candidate.purity:.2f}, intent match {candidate.intent_match:.2f})"
        for candidate in selected[: policy.target_count]
    )
    caveat = " Fewer verified regions than requested were found." if len(selected) < policy.target_count else ""
    return f"Verified regions: {findings}.{caveat}"


def run_query(query: dict[str, Any], prompt: str, tools: AtlasTools, client: OpenRouterClient, max_steps: int, seed: int, verbose: bool) -> dict[str, Any]:
    query_text = str(query.get("query") or "")
    policy = PilotPolicy(
        target_count=int(query.get("target_count") or 3),
        exploration=is_exploration_query(query_text),
        has_hard_constraints=has_hard_constraints(query_text),
        hard_constraint_text=query_text,
        structured_filters=extract_structured_filters(query_text),
    )
    messages: list[dict[str, Any]] = [{"role": "user", "content": query["query"]}]
    final_answer = ""
    tool_result_log: list[dict[str, Any]] = []
    started = time.time()

    for step in range(1, max_steps + 1):
        snapshot = policy.snapshot()
        if snapshot["must_stop"]:
            break
        data = client.chat(
            {
                "model": client.model,
                "messages": [
                    {"role": "system", "content": prompt},
                    *messages,
                    {
                        "role": "system",
                        "content": "SEARCH_POLICY_STATE (controller-enforced):\n"
                        + json.dumps(snapshot)
                        + "\nRespect remaining budgets. If must_stop=true, call save_results at most once if needed, then answer immediately.",
                    },
                ],
                "tools": TOOL_DEFINITIONS,
                "tool_choice": "auto",
                "temperature": 0,
                "max_tokens": 900,
                "reasoning": {"effort": "none", "exclude": True},
            },
            "Wine Atlas Agent PAR pilot",
        )
        policy.record_usage(data.get("usage"))
        choice = data.get("choices", [{}])[0]
        message = choice.get("message", {})
        tool_calls = message.get("tool_calls") or []
        if verbose:
            print(
                json.dumps(
                    {
                        "query_id": query["query_id"],
                        "step": step,
                        "finish_reason": choice.get("finish_reason"),
                        "tool_calls": [call.get("function", {}).get("name") for call in tool_calls],
                        "tokens": data.get("usage", {}).get("total_tokens"),
                        "must_stop": snapshot["must_stop"],
                        "stop_reason": snapshot["stop_reason"],
                    },
                    ensure_ascii=False,
                )
            )
        if not tool_calls:
            final_answer = message.get("content") or ""
            break

        messages.append({"role": "assistant", "content": message.get("content") or "", "tool_calls": tool_calls})
        stop_after_turn = False
        for call in tool_calls:
            allowed, blocked = policy.evaluate(call)
            if blocked:
                result = blocked
            else:
                result = tools.execute(allowed)
                policy.record_result(result)
            compact = compact_tool_result(result, policy)
            tool_result_log.append(compact)
            if verbose:
                print(json.dumps({"query_id": query["query_id"], "tool_result": compact}, ensure_ascii=False))
            messages.append(
                {
                    "role": "tool",
                    "tool_call_id": result["call_id"],
                    "content": json.dumps(tool_content_for_model(result, policy) if not result.get("error") else result.get("error"), ensure_ascii=False),
                }
            )
            if policy.stop_reason:
                stop_after_turn = True
                break
        if stop_after_turn:
            break

    if not final_answer:
        try:
            final_answer = force_final_answer(client, prompt, messages, policy)
        except RuntimeError as exc:
            policy.events.append({"tool": "final_answer", "status": "failed", "detail": str(exc)})
    final_answer = sanitize_final_answer(final_answer)
    if not final_answer:
        final_answer = fallback_final_answer(policy)

    latency_ms = int((time.time() - started) * 1000)
    snapshot = policy.snapshot()
    candidates = snapshot["candidates"]
    accepted = [item for item in candidates if item["recommended_action"] == "accept"]
    rejected = [item for item in candidates if item["recommended_action"] == "reject"]
    frontier = snapshot["frontier"]
    results = []
    rank = 1
    for candidate in accepted:
        for review_id in candidate.get("review_ids", []):
            results.append(
                {
                    "review_id": int(review_id),
                    "rank": rank,
                    "score": candidate.get("utility"),
                    "region_id": candidate.get("id"),
                    "theme": candidate.get("category"),
                    "title": None,
                    "description": None,
                }
            )
            rank += 1
    tool_sequence = [f"{event['tool']}:{event['status']}" for event in snapshot["trajectory"]]
    compact_candidate_fields = [
        "id",
        "category",
        "purity",
        "intent_match",
        "utility",
        "recommended_action",
        "acceptance_tier",
        "hard_constraint_match",
        "density",
        "projection_agreement",
        "review_ids",
    ]
    compact_accepted = [{key: item.get(key) for key in compact_candidate_fields} for item in accepted]
    compact_rejected = [{key: item.get(key) for key in compact_candidate_fields} for item in rejected]
    compact_frontier = [{key: item.get(key) for key in compact_candidate_fields} for item in frontier]
    record = {
        "query_id": query["query_id"],
        "tool_sequence": tool_sequence,
        "accepted": compact_accepted,
        "rejected": compact_rejected,
        "frontier": compact_frontier,
        "purity": {item["id"]: item["purity"] for item in candidates},
        "intent_match": {item["id"]: item["intent_match"] for item in candidates},
        "stop_reason": snapshot["stop_reason"],
        "final_answer": final_answer,
        "tokens": policy.model_tokens,
        "latency": latency_ms,
        "cost_usd": round(policy.model_cost, 6),
        "system_id": "par_pilot",
        "seed": seed,
        "results": results,
        "regions": [
            {
                "region_id": item["id"],
                "purity": item["purity"],
                "intent_match": item["intent_match"],
                "utility": item["utility"],
                "recommended_action": item["recommended_action"],
                "acceptance_tier": item.get("acceptance_tier"),
                "review_ids": item.get("review_ids", []),
            }
            for item in candidates
        ],
        "cost": {
            "latency_ms": latency_ms,
            "total_tokens": policy.model_tokens,
            "tool_calls": policy.tool_calls,
            "probes": policy.inspected_regions,
            "cost_usd": round(policy.model_cost, 6),
        },
        "trajectory": snapshot["trajectory"],
        "pilot": {
            "query": query["query"],
            "target_count": query.get("target_count"),
            "tool_sequence": tool_sequence,
            "accepted": accepted,
            "rejected": rejected,
            "frontier": frontier,
            "tool_results": tool_result_log,
            "final_answer": final_answer,
            "stable_pattern": stable_pattern(snapshot["trajectory"]),
        },
    }
    return record


def stable_pattern(events: list[dict[str, Any]]) -> bool:
    accepted_tools = [event["tool"] for event in events if event.get("status") == "accepted"]
    if not accepted_tools or accepted_tools[0] != "scan_regions":
        return False
    inspect_events = [event for event in events if event.get("tool") == "inspect_regions" and event.get("status") in {"accepted", "filtered"}]
    if not inspect_events:
        return False
    return any(len((event.get("parameters") or {}).get("regions", [])) >= 3 for event in inspect_events)


def is_exploration_query(query: str) -> bool:
    return bool(re.search(r"\b(explore|discover|find|map|regions?|themes?|styles?|different|distinct|diverse|unusual|open-ended)\b|探索|发现|地图|区域|主题|风格|不同|多样|少见", query, re.I))


def has_hard_constraints(query: str) -> bool:
    return bool(re.search(r"\b(red|white|rosé|rose|sparkling|under\s*\$?\d+|over\s*\$?\d+|less than\s*\$?\d+|more than\s*\$?\d+|from\s+[A-Z][a-z]+|only)\b|红葡萄酒|白葡萄酒|桃红|起泡|低于\s*\$?\d+|高于\s*\$?\d+", query, re.I))


def extract_structured_filters(query: str) -> dict[str, float]:
    filters: dict[str, float] = {}
    max_match = re.search(r"\b(?:under|below|less than)\s*\$?(\d+(?:\.\d+)?)|低于\s*\$?(\d+(?:\.\d+)?)", query, re.I)
    min_match = re.search(r"\b(?:over|above|more than)\s*\$?(\d+(?:\.\d+)?)|高于\s*\$?(\d+(?:\.\d+)?)", query, re.I)
    if max_match:
        filters["max_price"] = float(next(value for value in max_match.groups() if value is not None))
    if min_match:
        filters["min_price"] = float(next(value for value in min_match.groups() if value is not None))
    return filters


def violates_obvious_constraint(query: str, themes: list[str]) -> bool:
    query_lower = query.lower()
    evidence = " ".join(themes).lower()
    asks_red = bool(re.search(r"\bred(?:\s+wines?)?\b|红葡萄酒", query_lower))
    asks_white = bool(re.search(r"\bwhite(?:\s+wines?)?\b|白葡萄酒", query_lower))
    has_red = bool(re.search(r"\bred\b|红", evidence))
    has_white = bool(re.search(r"\bwhite\b|白", evidence))
    return (asks_red and not asks_white and has_white and not has_red) or (asks_white and not asks_red and has_red and not has_white)


def sanitize_final_answer(answer: str) -> str:
    markers = ["<｜DSML｜tool_calls>", "<ï½œDSMLï½œtool_calls>", "<|tool_calls|>"]
    cleaned = answer or ""
    for marker in markers:
        index = cleaned.find(marker)
        if index >= 0:
            cleaned = cleaned[:index]
    return cleaned.strip()


def write_jsonl(path: Path, records: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        for record in records:
            handle.write(json.dumps(record, ensure_ascii=False) + "\n")


def main() -> int:
    root = repo_root()
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--query-ids", nargs="+", default=DEFAULT_QUERY_IDS)
    parser.add_argument("--queries", type=Path, default=root / "benchmark" / "queries" / "queries_v1.jsonl")
    parser.add_argument("--data", type=Path, default=root / "web-app" / "public" / "atlas" / "data" / "dataset.parquet")
    parser.add_argument("--env", type=Path, default=root / "web-app" / ".env.local")
    parser.add_argument("--output", type=Path, default=root / "benchmark" / "runs" / "pilot" / f"par_pilot_{timestamp}.jsonl")
    parser.add_argument("--summary", type=Path, default=root / "benchmark" / "reports" / f"par_pilot_{timestamp}.json")
    parser.add_argument("--max-steps", type=int, default=8)
    parser.add_argument("--sample-size", type=int, default=8)
    parser.add_argument("--analyzer-model", type=str, help="Override the model used only for per-region Analyzer calls.")
    parser.add_argument(
        "--request-timeout",
        type=int,
        default=45,
        help="Per-request OpenRouter timeout in seconds (default: 45).",
    )
    parser.add_argument("--seed", type=int, default=43)
    parser.add_argument("--verbose", action="store_true")
    args = parser.parse_args()

    env = load_env(args.env)
    api_key = os.environ.get("OPENROUTER_API_KEY") or env.get("OPENROUTER_API_KEY")
    model = os.environ.get("OPENROUTER_MODEL") or env.get("OPENROUTER_MODEL")
    if not api_key or not model:
        raise RuntimeError("OPENROUTER_API_KEY and OPENROUTER_MODEL must be set in env or web-app/.env.local")

    prompt = load_prompt(root / "web-app" / "api" / "agentPrompt.ts")
    queries = load_queries(args.queries, args.query_ids)
    random.seed(args.seed)
    analyzer_model = args.analyzer_model or os.environ.get("OPENROUTER_ANALYZER_MODEL") or env.get("OPENROUTER_ANALYZER_MODEL") or model
    client = OpenRouterClient(api_key=api_key, model=model, timeout=args.request_timeout)
    analyzer_client = OpenRouterClient(api_key=api_key, model=analyzer_model, timeout=args.request_timeout)
    tools = AtlasTools(data_path=args.data, client=analyzer_client, sample_size=args.sample_size, seed=args.seed)

    records = []
    for query in queries:
        print(f"Running {query['query_id']}: {query['query']}", flush=True)
        record = run_query(query, prompt, tools, client, args.max_steps, args.seed, args.verbose)
        records.append(record)
        print(
            json.dumps(
                {
                    "query_id": record["query_id"],
                    "stable_pattern": record["pilot"]["stable_pattern"],
                    "accepted": len(record["pilot"]["accepted"]),
                    "rejected": len(record["pilot"]["rejected"]),
                    "frontier": len(record["pilot"]["frontier"]),
                    "stop_reason": record["stop_reason"],
                    "tokens": record["cost"]["total_tokens"],
                    "cost_usd": record["cost"].get("cost_usd"),
                    "latency_ms": record["cost"]["latency_ms"],
                },
                ensure_ascii=False,
            ),
            flush=True,
        )

    write_jsonl(args.output, records)
    summary = {
        "created_at": timestamp,
        "model": model,
        "analyzer_model": analyzer_model,
        "output": str(args.output),
        "queries": [
            {
                "query_id": record["query_id"],
                "stable_pattern": record["pilot"]["stable_pattern"],
                "accepted": len(record["pilot"]["accepted"]),
                "rejected": len(record["pilot"]["rejected"]),
                "frontier": len(record["pilot"]["frontier"]),
                "stop_reason": record["stop_reason"],
                "final_answer_present": bool(record["pilot"]["final_answer"].strip()),
                "tokens": record["cost"]["total_tokens"],
                "latency_ms": record["cost"]["latency_ms"],
                "cost_usd": record["cost"].get("cost_usd"),
            }
            for record in records
        ],
        "totals": {
            "tokens": sum(record["cost"]["total_tokens"] for record in records),
            "cost_usd": round(sum(record["cost"].get("cost_usd", 0) for record in records), 6),
            "latency_ms": sum(record["cost"]["latency_ms"] for record in records),
        },
    }
    args.summary.parent.mkdir(parents=True, exist_ok=True)
    args.summary.write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"Wrote runs: {args.output}")
    print(f"Wrote summary: {args.summary}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
