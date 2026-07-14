#!/usr/bin/env python3
"""Run the locked football-count vNext shadow publication and tracking stack."""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "scripts"
FORM = ROOT / "data" / "football-form"


def run(*args: str) -> None:
    command = [sys.executable, *args]
    print(">", " ".join(command))
    subprocess.run(command, cwd=ROOT, check=True)


def main() -> int:
    run(str(SCRIPTS / "publish-football-vnext-shadow.py"))
    run(
        str(SCRIPTS / "team-shots-v1-clv-monitor.py"),
        "--picks", str(FORM / "team-shots-v4-shadow-signals.csv"),
        "--output", str(FORM / "team-shots-v4-shadow-clv.csv"),
        "--report", str(FORM / "team-shots-v4-shadow-clv.md"),
        "--allowed-config", str(FORM / "team-shots-v4-shadow-config.json"),
    )
    run(
        str(SCRIPTS / "corners-v0-clv-monitor.py"),
        "--picks", str(FORM / "corners-v3-shadow-signals.csv"),
        "--output", str(FORM / "corners-v3-shadow-clv.csv"),
        "--report", str(FORM / "corners-v3-shadow-clv.md"),
        "--allowed-config", str(FORM / "corners-v3-shadow-config.json"),
    )
    run(
        str(SCRIPTS / "settle-football-research-lanes.py"),
        "--team-shots", str(FORM / "team-shots-v4-shadow-clv.csv"),
        "--corners", str(FORM / "corners-v3-shadow-clv.csv"),
        "--team-audit", str(FORM / "team-shots-v4-settlement-audit.json"),
        "--corners-audit", str(FORM / "corners-v3-settlement-audit.json"),
        "--team-model", "team-shots-v4-shadow",
        "--corners-model", "corners-v3-shadow",
    )
    run(str(SCRIPTS / "football-counts-vnext-gate.py"))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
