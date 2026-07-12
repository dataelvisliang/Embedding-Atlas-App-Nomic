#!/usr/bin/env python3
"""Extract the SearchPolicy JSON block from an exported chat Markdown file."""
from __future__ import annotations

import argparse
import json
import re
from pathlib import Path


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("markdown", type=Path)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    text = args.markdown.read_text(encoding="utf-8")
    match = re.search(r"## Search policy trajectory\s+```json\s*([\s\S]*?)\s*```", text)
    if not match:
        raise SystemExit("No Search policy trajectory JSON block found")
    payload = json.loads(match.group(1))
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    print(f"Wrote {args.output}")


if __name__ == "__main__":
    main()
