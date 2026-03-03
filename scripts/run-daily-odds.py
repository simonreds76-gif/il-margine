#!/usr/bin/env python3
"""
Run Pinnacle scraper then fair-odds pipeline in sequence.
Use when you want fresh bookmaker odds + fair odds in one go.

For Pinnacle to show on the fair-odds page (localhost):
  - .env.local must have NEXT_PUBLIC_SUPABASE_URL and SUPABASE_SERVICE_ROLE_KEY
    (scraper uses these to write to bookmaker_odds_snapshot; API uses service role to read).
  - This script runs the scraper without --dry-run, so it upserts to Supabase.
  - After running, refresh /fair-odds. If Pin column still shows '—', check scraper
    output for "Upserted N rows" (N > 0) and that next dev has SUPABASE_SERVICE_ROLE_KEY.
"""
import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

def main():
    print("=== 1/2 Pinnacle scraper (writes to bookmaker_odds_snapshot) ===\n")
    r1 = subprocess.run(
        [sys.executable, str(ROOT / "scripts" / "pinnacle-scrape-odds.py")],
        cwd=str(ROOT),
        env=os.environ.copy(),
    )
    if r1.returncode != 0:
        print("\nPinnacle scraper failed. Stopping.")
        sys.exit(r1.returncode)

    print("\n=== 2/2 Fair odds pipeline ===\n")
    r2 = subprocess.run(
        [sys.executable, str(ROOT / "scripts" / "oncourt-compute-fair-odds.py")],
        cwd=str(ROOT),
    )
    if r2.returncode != 0:
        print("\nFair-odds pipeline failed.")
        sys.exit(r2.returncode)

    print("\nDone. Pinnacle snapshot + daily_fair_odds updated.")

if __name__ == "__main__":
    main()
