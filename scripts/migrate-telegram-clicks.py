#!/usr/bin/env python3
"""Apply the first-party Telegram click-tracking migration."""
from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
MIGRATION = ROOT / "db" / "migrations" / "20260821_0001_telegram_clicks.sql"
ENV_FILES = (ROOT / ".env.local", ROOT / "env.local", ROOT / ".env")


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


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    sql = MIGRATION.read_text(encoding="utf-8")
    if args.dry_run:
        print(sql)
        return 0

    load_env_files()
    dsn = (os.environ.get("DATABASE_URL") or os.environ.get("SUPABASE_DB_URL") or "").strip()
    if not dsn:
        print("DATABASE_URL or SUPABASE_DB_URL is required.", file=sys.stderr)
        return 2

    try:
        import psycopg2
    except ImportError:
        print("psycopg2-binary is required.", file=sys.stderr)
        return 2

    with psycopg2.connect(dsn, connect_timeout=10) as conn:
        with conn.cursor() as cur:
            cur.execute(sql)

    print("Applied Telegram click-tracking migration.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
