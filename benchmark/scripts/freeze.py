#!/usr/bin/env python3
"""Create a SHA-256 manifest for files that define benchmark v1."""
from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
FILES = [
    "benchmark/queries/queries_v1.jsonl",
    "benchmark/configs/benchmark_v1.json",
    "benchmark/configs/systems.json",
    "benchmark/configs/par_v1.json",
    "benchmark/schemas/run.schema.json",
    "benchmark/schemas/judgment.schema.json",
]


def main():
    hashes = {}
    for relative in FILES:
        data = (ROOT / relative).read_bytes()
        hashes[relative] = hashlib.sha256(data).hexdigest()
    manifest = {
        "benchmark_id": "wine-par-v1",
        "created_at_utc": datetime.now(timezone.utc).isoformat(),
        "hash_algorithm": "sha256",
        "files": hashes,
    }
    output = ROOT / "benchmark" / "frozen_manifest_v1.json"
    output.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    print(f"Wrote {output}")


if __name__ == "__main__":
    main()
