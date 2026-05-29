#!/usr/bin/env python3
"""Apply daily_fair_odds raw-probability columns for calibration overlays."""
from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MIGRATION = ROOT / "db" / "migrations" / "20260529_0002_daily_fair_odds_raw_probs.sql"
ENV_FILES = (ROOT / ".env.local", ROOT / ".env", ROOT / "env.local")


def load_env_files() -> None:
    for path in ENV_FILES:
        if not path.exists():
            continue
        for raw_line in path.read_text(encoding="utf-8").splitlines():
            line = raw_line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, value = line.split("=", 1)
            key = key.strip()
            if key and key not in os.environ:
                os.environ[key] = value.strip().strip('"').strip("'")


def db_dsn() -> str | None:
    return os.environ.get("DATABASE_URL") or os.environ.get("SUPABASE_DB_URL")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dry-run", action="store_true", help="Print SQL without applying it.")
    args = parser.parse_args()

    if not MIGRATION.exists():
        print(f"Migration file missing: {MIGRATION}", file=sys.stderr)
        return 2

    sql = MIGRATION.read_text(encoding="utf-8")
    if args.dry_run:
        print(sql)
        return 0

    load_env_files()
    dsn = db_dsn()
    if not dsn:
        print("DATABASE_URL or SUPABASE_DB_URL is required to apply this schema migration.", file=sys.stderr)
        return 2

    try:
        import psycopg2
    except ImportError:
        print("psycopg2 is required. Install scripts/requirements.txt or psycopg2-binary.", file=sys.stderr)
        return 2

    with psycopg2.connect(dsn, connect_timeout=10) as conn:
        with conn.cursor() as cur:
            cur.execute(sql)

    print("Applied daily_fair_odds raw-probability migration.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
