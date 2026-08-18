#!/usr/bin/env python3
"""Fail-closed integrity helpers for registered model experiments."""

from __future__ import annotations

import hashlib
import json
import math
from pathlib import Path
from statistics import pstdev
from typing import Iterable, Sequence


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def verify_locked_input(lock_path: Path, input_name: str, actual_path: Path) -> str:
    if not lock_path.exists():
        raise RuntimeError(f"Missing experiment lock: {lock_path}")
    payload = json.loads(lock_path.read_text(encoding="utf-8"))
    expected = (((payload.get("input_files") or {}).get(input_name) or {}).get("sha256") or "").strip().lower()
    if not expected:
        raise RuntimeError(f"Lock {lock_path} has no SHA-256 for input {input_name}")
    if not actual_path.exists():
        raise RuntimeError(f"Missing registered input {input_name}: {actual_path}")
    actual = sha256_file(actual_path)
    if actual != expected:
        raise RuntimeError(
            f"Registered input mismatch for {input_name}: expected {expected}, got {actual}. "
            "Regenerate the canonical input before running this experiment."
        )
    return actual


def assert_variable_columns(
    rows: Iterable[Sequence[float]],
    names: Sequence[str],
    *,
    tolerance: float = 1e-12,
) -> None:
    materialized = [tuple(float(value) for value in row) for row in rows]
    if not materialized:
        raise RuntimeError("Cannot fit a registered model with no feature rows")
    if any(len(row) != len(names) for row in materialized):
        raise RuntimeError("Feature row width does not match registered feature names")
    columns = list(zip(*materialized))
    bad = [
        name
        for name, column in zip(names, columns)
        if any(not math.isfinite(value) for value in column) or pstdev(column) <= tolerance
    ]
    if bad:
        raise RuntimeError(f"Constant or invalid registered feature column(s): {', '.join(bad)}")
