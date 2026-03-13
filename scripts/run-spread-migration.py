#!/usr/bin/env python3
"""
Run the bookmaker_odds_snapshot spread columns migration.

Requires DATABASE_URL in .env.local (Supabase direct Postgres connection string).
Get it from: Supabase Dashboard -> Project Settings -> Database -> Connection string (URI).

Usage:
  python scripts/run-spread-migration.py
"""

import os
import sys
from pathlib import Path

# Load .env.local
root = Path(__file__).resolve().parent.parent
for name in [".env.local", "env.local", ".env"]:
    path = root / name
    if path.exists():
        for line in path.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                k, v = line.split("=", 1)
                os.environ[k.strip()] = v.strip().strip('"').strip("'")
        break

DATABASE_URL = os.environ.get("DATABASE_URL") or os.environ.get("SUPABASE_DB_URL")

SQL = """
ALTER TABLE public.bookmaker_odds_snapshot
  ADD COLUMN IF NOT EXISTS spread_line numeric,
  ADD COLUMN IF NOT EXISTS spread_odds1 numeric,
  ADD COLUMN IF NOT EXISTS spread_odds2 numeric;
"""


def main():
    if not DATABASE_URL:
        print("  DATABASE_URL not set. To run migration automatically:")
        print("  1. Supabase Dashboard -> Project Settings -> Database")
        print("  2. Copy 'Connection string' (URI) - use 'Transaction' mode")
        print("  3. Add to .env.local: DATABASE_URL=postgresql://...")
        print()
        print("  Or run manually in Supabase SQL Editor:")
        print("  docs/supabase-bookmaker-spread-columns.sql")
        sys.exit(1)

    try:
        import psycopg2
    except ImportError:
        print("  psycopg2 not installed. Run: pip install psycopg2-binary")
        sys.exit(1)

    try:
        conn = psycopg2.connect(DATABASE_URL)
        conn.autocommit = True
        cur = conn.cursor()
        cur.execute(SQL)
        cur.close()
        conn.close()
        print("  Migration OK: spread_line, spread_odds1, spread_odds2 added.")
    except Exception as e:
        print(f"  Migration failed: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
