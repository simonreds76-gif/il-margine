#!/usr/bin/env python3
"""Fail if penalty-taker JSON files contain common UTF-8 mojibake."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

BAD_CODEPOINTS = {0x00C2, 0x00C3, 0x00E2, 0xFFFD}
PENALTY_FILES = sorted(Path("data/goalscorer").glob("*-penalty-takers.json"))


def has_mojibake(value: str) -> bool:
    return any(ord(char) in BAD_CODEPOINTS or 0x0080 <= ord(char) <= 0x009F for char in value)


def walk(value: Any, path: str) -> list[tuple[str, str]]:
    if isinstance(value, dict):
        hits: list[tuple[str, str]] = []
        for key, item in value.items():
            if isinstance(key, str) and has_mojibake(key):
                hits.append((f"{path}.{key}", key))
            hits.extend(walk(item, f"{path}.{key}"))
        return hits

    if isinstance(value, list):
        hits: list[tuple[str, str]] = []
        for index, item in enumerate(value):
            hits.extend(walk(item, f"{path}[{index}]"))
        return hits

    if isinstance(value, str) and has_mojibake(value):
        return [(path, value)]

    return []


def main() -> int:
    all_hits: list[tuple[str, str]] = []

    for file_path in PENALTY_FILES:
        data = json.loads(file_path.read_text(encoding="utf-8"))
        all_hits.extend((f"{file_path}:{field_path}", value) for field_path, value in walk(data, "$"))

    if not all_hits:
        print("[penalty-mojibake] ok")
        return 0

    print("[penalty-mojibake] found corrupted text:")
    for field_path, value in all_hits:
        print(f"  {field_path}: {value!r}")
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
