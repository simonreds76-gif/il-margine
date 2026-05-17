#!/usr/bin/env python3
"""Run the private Assist Value shadow lane.

The lane is deliberately evidence-only:
  1. optionally refresh set-piece role source audit data
  2. scrape Bet365 assist markets from odds-api.io into data/assist-value/inbox
  3. enrich captured odds with role shares into a private shadow board
"""

from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_LEAGUES = ["serie-a", "epl", "la-liga", "bundesliga", "ligue-1"]


def run_cmd(cmd: list[str], *, allow_failure: bool = False) -> bool:
    print("  >", " ".join(cmd))
    result = subprocess.run(cmd, cwd=ROOT, check=False)
    if result.returncode == 0:
        return True
    if allow_failure:
        print(f"  WARNING: command failed with exit {result.returncode}; continuing.")
        return False
    raise subprocess.CalledProcessError(result.returncode, cmd)


def parse_leagues(raw: str) -> list[str]:
    leagues = [item.strip() for item in raw.split(",") if item.strip()]
    return leagues or DEFAULT_LEAGUES


def main() -> None:
    parser = argparse.ArgumentParser(description="Run private Assist Value shadow lane")
    parser.add_argument("--leagues", default=",".join(DEFAULT_LEAGUES))
    parser.add_argument("--bookmakers", default="Bet365")
    parser.add_argument("--days-ahead", type=int, default=3)
    parser.add_argument("--refresh-role-sources", action="store_true")
    parser.add_argument("--skip-odds", action="store_true")
    parser.add_argument("--allow-odds-failure", action="store_true")
    args = parser.parse_args()

    print("\n" + "=" * 64)
    print("  IL MARGINE - Assist Value Shadow")
    print("=" * 64)
    print("  Status: research-only, no public lane, no model wiring")

    if args.refresh_role_sources:
        run_cmd(
            [
                sys.executable,
                str(ROOT / "scripts" / "audit-assist-setpiece-sources.py"),
                "--out-dir",
                str(ROOT / "data" / "assist-value"),
            ]
        )

    if not args.skip_odds:
        for league in parse_leagues(args.leagues):
            run_cmd(
                [
                    sys.executable,
                    str(ROOT / "scripts" / "odds-api-scrape-assists.py"),
                    "--league",
                    league,
                    "--bookmakers",
                    args.bookmakers,
                    "--days-ahead",
                    str(args.days_ahead),
                    "--out-dir",
                    str(ROOT / "data" / "assist-value" / "inbox"),
                    "--market-audit-out",
                    str(ROOT / "data" / "assist-value" / f"assist-market-audit-{league}.csv"),
                ],
                allow_failure=args.allow_odds_failure,
            )

    run_cmd(
        [
            sys.executable,
            str(ROOT / "scripts" / "build-assist-value-shadow.py"),
            "--odds-input",
            "data/assist-value/inbox/*.csv",
            "--roles",
            "data/assist-value/rotowire-setpiece-roles.csv",
            "--out",
            "data/assist-value/assist-value-shadow-board.csv",
            "--report-out",
            "data/assist-value/assist-value-shadow-report.txt",
        ]
    )

    print("\n  Done.\n")


if __name__ == "__main__":
    main()
