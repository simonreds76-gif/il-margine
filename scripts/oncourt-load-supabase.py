"""
Phase 1.3: Load OnCourt CSVs into Supabase via PostgREST API.

Usage:
  python scripts/oncourt-load-supabase.py          # full load (first time)
  python scripts/oncourt-load-supabase.py --quick   # daily: players/tours/today only
  python scripts/oncourt-load-supabase.py --recent  # last 365 days of games/stat

Uses requests (no supabase pip package needed).
Reads credentials from .env.local in project root.
"""

import csv
import os
import sys
import time
from datetime import datetime, timedelta
from pathlib import Path
from time import sleep as _sleep

import requests

# ─── Environment ────────────────────────────────────────────────────

ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = ROOT / "data" / "oncourt"
BATCH = 5000

QUICK = "--quick" in sys.argv
RECENT = "--recent" in sys.argv
RECENT_DAYS = 365


def _load_env():
    for name in [".env.local", "env.local"]:
        path = ROOT / name
        if path.exists():
            for line in path.read_text(encoding="utf-8").splitlines():
                line = line.strip()
                if line and not line.startswith("#") and "=" in line:
                    k, v = line.split("=", 1)
                    os.environ.setdefault(k.strip(), v.strip().strip('"').strip("'"))

_load_env()

SUPABASE_URL = (
    os.environ.get("NEXT_PUBLIC_SUPABASE_URL")
    or os.environ.get("SUPABASE_URL")
    or ""
).rstrip("/")
SUPABASE_KEY = (
    os.environ.get("SUPABASE_SERVICE_ROLE_KEY")
    or os.environ.get("NEXT_PUBLIC_SUPABASE_ANON_KEY")
    or ""
)

# ─── Helpers ────────────────────────────────────────────────────────


def load_csv(path):
    if not path.exists():
        print(f"  WARNING: {path} not found, skipping")
        return []
    with open(path, "r", encoding="utf-8") as f:
        return list(csv.DictReader(f))


def _headers():
    return {
        "apikey": SUPABASE_KEY,
        "Authorization": f"Bearer {SUPABASE_KEY}",
        "Content-Type": "application/json",
    }


def _upsert(table: str, data: list, on_conflict: str, retries: int = 3):
    """POST to PostgREST with merge-duplicates upsert."""
    url = f"{SUPABASE_URL}/rest/v1/{table}?on_conflict={on_conflict}"
    hdrs = _headers()
    hdrs["Prefer"] = "resolution=merge-duplicates,return=minimal"

    for attempt in range(1, retries + 1):
        try:
            resp = requests.post(url, json=data, headers=hdrs, timeout=120)
            if resp.ok:
                return True
            if resp.status_code == 409:
                print(f"    409 Conflict on {table}. Ensure UNIQUE constraint on ({on_conflict}).")
                return False
            print(f"    WARNING: {table} upsert {resp.status_code}: {resp.text[:200]} (attempt {attempt})")
        except requests.RequestException as e:
            print(f"    WARNING: {table} network error (attempt {attempt}): {e}")
        if attempt < retries:
            _sleep(2 ** attempt)
    print(f"    ERROR: {table} upsert failed after {retries} attempts")
    return False


def _delete_all(table: str):
    """Delete all rows from a table."""
    url = f"{SUPABASE_URL}/rest/v1/{table}?tour_id=neq.-1"
    resp = requests.delete(url, headers=_headers(), timeout=30)
    return resp.ok


def _insert(table: str, data: list, retries: int = 3):
    """Plain INSERT (no upsert)."""
    url = f"{SUPABASE_URL}/rest/v1/{table}"
    hdrs = _headers()
    hdrs["Prefer"] = "return=minimal"
    for attempt in range(1, retries + 1):
        try:
            resp = requests.post(url, json=data, headers=hdrs, timeout=120)
            if resp.ok:
                return True
            print(f"    WARNING: {table} insert {resp.status_code}: {resp.text[:200]} (attempt {attempt})")
        except requests.RequestException as e:
            print(f"    WARNING: {table} network error (attempt {attempt}): {e}")
        if attempt < retries:
            _sleep(2 ** attempt)
    return False


def _safe_int(val, default=0):
    try:
        return int(val) if val else default
    except (ValueError, TypeError):
        return default


def _dedup(data, key_cols):
    """Remove duplicate rows within a batch (PostgREST rejects same key twice in one request)."""
    seen = set()
    out = []
    keys = [k.strip() for k in key_cols.split(",")]
    for row in data:
        k = tuple(row.get(c) for c in keys)
        if k not in seen:
            seen.add(k)
            out.append(row)
    return out


def _upload_batched(table, rows, on_conflict, transform_fn, label=None):
    """Upload rows in batches with progress reporting and deduplication."""
    label = label or table
    total = len(rows)
    if total == 0:
        print(f"  {label}: 0 rows (skipped)")
        return
    t0 = time.time()
    ok_count = 0
    dups_removed = 0
    for i in range(0, total, BATCH):
        batch = rows[i : i + BATCH]
        data = [transform_fn(r) for r in batch]
        before = len(data)
        data = _dedup(data, on_conflict)
        dups_removed += before - len(data)
        ok = _upsert(table, data, on_conflict)
        if not ok:
            _insert(table, data)
        ok_count += len(batch)
        elapsed = time.time() - t0
        rate = ok_count / elapsed if elapsed > 0 else 0
        eta = (total - ok_count) / rate if rate > 0 else 0
        print(f"  {label}: {ok_count:,} / {total:,}  ({rate:.0f} rows/s, ~{eta:.0f}s left)")
    elapsed = time.time() - t0
    extra = f" ({dups_removed:,} duplicates skipped)" if dups_removed else ""
    print(f"  {label}: {total:,} rows done in {elapsed:.1f}s{extra}")


# ─── Main ───────────────────────────────────────────────────────────


def main():
    if not SUPABASE_URL or not SUPABASE_KEY:
        print("ERROR: Missing Supabase credentials.")
        print("  Ensure .env.local has NEXT_PUBLIC_SUPABASE_URL and")
        print("  SUPABASE_SERVICE_ROLE_KEY (or NEXT_PUBLIC_SUPABASE_ANON_KEY)")
        sys.exit(1)

    key_type = "service_role" if os.environ.get("SUPABASE_SERVICE_ROLE_KEY") else "anon"
    mode = "QUICK (players/tours/today only)" if QUICK else "RECENT (last 365d games/stat)" if RECENT else "FULL"
    print(f"  Supabase: {SUPABASE_URL[:40]}... (key: {key_type})")
    print(f"  Mode: {mode}  |  Batch: {BATCH:,}")
    print()

    tours_rows = load_csv(DATA_DIR / "tours_atp.csv")
    tour_date = {r["id"]: r["date"] for r in tours_rows if r.get("date")}

    # 1. Courts
    rows = load_csv(DATA_DIR / "courts.csv")
    if rows:
        data = [{"id": _safe_int(r["id"]), "name": r["name"]} for r in rows]
        _upsert("oncourt_courts", data, "id")
        print(f"  oncourt_courts: {len(data)} rows")

    # 2. Players
    _upload_batched(
        "oncourt_players",
        load_csv(DATA_DIR / "players_atp.csv"),
        "id",
        lambda r: {
            "id": _safe_int(r["id"]),
            "name": r.get("name", ""),
            "birthdate": r.get("birthdate") or None,
            "country": r.get("country", ""),
        },
    )

    # 3. Tours
    _upload_batched(
        "oncourt_tours",
        tours_rows,
        "id",
        lambda r: {
            "id": _safe_int(r["id"]),
            "name": r.get("name", ""),
            "court_id": _safe_int(r.get("court_id"), None),
            "date": r.get("date") or None,
            "rank": _safe_int(r.get("rank"), None),
            "country": r.get("country", ""),
        },
    )

    # 4. Games (skip in --quick mode)
    if QUICK:
        print("  oncourt_games: SKIPPED (--quick mode)")
    else:
        rows = load_csv(DATA_DIR / "games_atp.csv")
        if RECENT:
            cutoff = (datetime.now() - timedelta(days=RECENT_DAYS)).strftime("%Y-%m-%d")
            before = len(rows)
            rows = [r for r in rows if (r.get("date") or tour_date.get(r.get("tour_id", ""), "")) >= cutoff]
            print(f"  oncourt_games: filtered {before:,} → {len(rows):,} (since {cutoff})")
        _upload_batched(
            "oncourt_games",
            rows,
            "winner_id,loser_id,tour_id,round_id",
            lambda r: {
                "winner_id": _safe_int(r["winner_id"]),
                "loser_id": _safe_int(r["loser_id"]),
                "tour_id": _safe_int(r.get("tour_id", "0")),
                "round_id": _safe_int(r.get("round_id")),
                "result": r.get("result", ""),
                "date": r.get("date") or tour_date.get(r.get("tour_id", "")),
            },
        )

    # 5. Stat (skip in --quick mode)
    if QUICK:
        print("  oncourt_stat: SKIPPED (--quick mode)")
    else:
        rows = load_csv(DATA_DIR / "stat_atp.csv")
        if RECENT:
            cutoff = (datetime.now() - timedelta(days=RECENT_DAYS)).strftime("%Y-%m-%d")
            before = len(rows)
            rows = [r for r in rows if tour_date.get(r.get("tour_id", ""), "") >= cutoff]
            print(f"  oncourt_stat: filtered {before:,} → {len(rows):,} (since {cutoff})")
        _upload_batched(
            "oncourt_stat",
            rows,
            "winner_id,loser_id,tour_id,round_id",
            lambda r: {
                "winner_id": _safe_int(r["winner_id"]),
                "loser_id": _safe_int(r["loser_id"]),
                "tour_id": _safe_int(r["tour_id"]),
                "round_id": _safe_int(r["round_id"]),
                "w_fs": _safe_int(r.get("w_fs")),
                "w_fsof": _safe_int(r.get("w_fsof")),
                "w_w1s": _safe_int(r.get("w_w1s")),
                "w_w1sof": _safe_int(r.get("w_w1sof")),
                "w_w2s": _safe_int(r.get("w_w2s")),
                "w_w2sof": _safe_int(r.get("w_w2sof")),
                "w_rpw": _safe_int(r.get("w_rpw")),
                "w_rpwof": _safe_int(r.get("w_rpwof")),
                "l_fs": _safe_int(r.get("l_fs")),
                "l_fsof": _safe_int(r.get("l_fsof")),
                "l_w1s": _safe_int(r.get("l_w1s")),
                "l_w1sof": _safe_int(r.get("l_w1sof")),
                "l_w2s": _safe_int(r.get("l_w2s")),
                "l_w2sof": _safe_int(r.get("l_w2sof")),
                "l_rpw": _safe_int(r.get("l_rpw")),
                "l_rpwof": _safe_int(r.get("l_rpwof")),
            },
        )

    # 6. Today (delete + insert fresh)
    rows = load_csv(DATA_DIR / "today_atp.csv")
    if rows:
        data = [
            {
                "tour_id": _safe_int(r["tour_id"]),
                "player1_id": _safe_int(r["player1_id"]),
                "player2_id": _safe_int(r["player2_id"]),
                "round_id": _safe_int(r.get("round_id")),
                "draw": _safe_int(r.get("draw")),
                "result": r.get("result", ""),
            }
            for r in rows
        ]
        _delete_all("oncourt_today")
        _insert("oncourt_today", data)
        print(f"  oncourt_today: {len(data)} rows")

    print("\nDone.")


if __name__ == "__main__":
    main()
