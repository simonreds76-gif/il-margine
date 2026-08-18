"""
Phase 1.3: Load OnCourt CSVs into Supabase via PostgREST API.

Usage:
  python scripts/oncourt-load-supabase.py          # full load (first time)
  python scripts/oncourt-load-supabase.py --quick   # daily: players/tours/today only
  python scripts/oncourt-load-supabase.py --quick --current-players  # daily: current fixture players/tours/today
  python scripts/oncourt-load-supabase.py --quick --skip-players  # daily: tours/today only
  python scripts/oncourt-load-supabase.py --recent  # last 365 days of games/stat
  python scripts/oncourt-load-supabase.py --batch 10000   # larger batches (faster, may hit limits)

Default batch: 5,000 rows. Use --batch N to try larger (e.g. 10000) for faster loads.
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
MIGRATION_SQL = ROOT / "docs" / "supabase-player-hand-reference-fix.sql"
HAND_SOURCE_CANDIDATES = (
    "oncourt",
    "categories_atp",
    "oncourt_categories",
    "manual",
    "atp",
    "import",
    "script",
)

QUICK = "--quick" in sys.argv
RECENT = "--recent" in sys.argv
SKIP_PLAYERS = "--skip-players" in sys.argv
CURRENT_PLAYERS_ONLY = "--current-players" in sys.argv
RECENT_DAYS = 365

# Batch size: 5k default. Try --batch 10000 for faster loads (Supabase may allow up to 10k).
def _parse_batch():
    for i, a in enumerate(sys.argv):
        if a == "--batch" and i + 1 < len(sys.argv):
            try:
                return int(sys.argv[i + 1])
            except ValueError:
                pass
    return 5000

BATCH = _parse_batch()


def _load_env():
    for name in [".env.local", "env.local"]:
        path = ROOT / name
        if path.exists():
            for line in path.read_text(encoding="utf-8").splitlines():
                line = line.strip()
                if line and not line.startswith("#") and "=" in line:
                    k, v = line.split("=", 1)
                    key = k.strip()
                    value = v.strip().strip('"').strip("'")
                    if not os.environ.get(key):
                        os.environ[key] = value

_load_env()

SUPABASE_URL = (
    os.environ.get("NEXT_PUBLIC_SUPABASE_URL")
    or os.environ.get("SUPABASE_URL")
    or ""
).rstrip("/")
SUPABASE_SERVICE_ROLE_KEY = os.environ.get("SUPABASE_SERVICE_ROLE_KEY") or ""
SUPABASE_ANON_KEY = os.environ.get("NEXT_PUBLIC_SUPABASE_ANON_KEY") or ""
SUPABASE_KEY = SUPABASE_SERVICE_ROLE_KEY or SUPABASE_ANON_KEY

# ─── Helpers ────────────────────────────────────────────────────────


def load_csv(path):
    if not path.exists():
        print(f"  WARNING: {path} not found, skipping")
        return []
    with open(path, "r", encoding="utf-8") as f:
        return list(csv.DictReader(f))


def current_fixture_player_rows(players_rows, today_rows):
    """Return the player records referenced by the current OnCourt fixture export."""
    current_ids = {
        str(row.get(field) or "").strip()
        for row in today_rows
        for field in ("player1_id", "player2_id")
        if str(row.get(field) or "").strip()
    }
    return [row for row in players_rows if str(row.get("id") or "").strip() in current_ids]


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


def _safe_float(val, default=None):
    try:
        if val is None or val == "":
            return default
        return float(val)
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


def _load_known_player_ids(data_dir):
    path = data_dir / "players_atp.csv"
    if not path.exists():
        return set()
    ids = set()
    with open(path, "r", encoding="utf-8-sig", newline="") as f:
        for row in csv.DictReader(f):
            pid = row.get("id")
            if not pid:
                continue
            try:
                ids.add(int(pid))
            except ValueError:
                continue
    return ids


def _run_hand_reference_migration():
    """Run migration via psycopg2 if DATABASE_URL is set. Returns True if run successfully."""
    db_url = os.environ.get("DATABASE_URL") or os.environ.get("SUPABASE_DB_URL")
    if not db_url or not MIGRATION_SQL.exists():
        return False
    try:
        import psycopg2
        sql = MIGRATION_SQL.read_text(encoding="utf-8")
        conn = psycopg2.connect(db_url)
        conn.autocommit = True
        cur = conn.cursor()
        cur.execute(sql)
        cur.close()
        conn.close()
        print("  Applied player_hand_reference fix (DATABASE_URL).")
        return True
    except Exception as e:
        print(f"  Migration failed: {e}")
        return False


def _is_source_constraint_error(text: str) -> bool:
    if not text:
        return False
    t = text.lower()
    return (
        "player_hand_reference_source_check" in t
        or ("source" in t and "check" in t)
        or 'null value in column "source"' in t
    )


def _is_source_column_missing_error(text: str) -> bool:
    if not text:
        return False
    t = text.lower()
    return 'column "source" does not exist' in t


def _player_hand_payload(rows, source_value):
    if source_value is None:
        return [{"player_id": r["player_id"], "hand": "L"} for r in rows]
    return [{"player_id": r["player_id"], "hand": "L", "source": source_value} for r in rows]


def _post_player_hand_rows(rows, source_value, retries=2):
    url = f"{SUPABASE_URL}/rest/v1/player_hand_reference?on_conflict=player_id"
    payload = _player_hand_payload(rows, source_value)
    hdrs = _headers()
    hdrs["Prefer"] = "resolution=merge-duplicates,return=minimal"
    last_status = 0
    last_text = ""
    for attempt in range(1, retries + 1):
        try:
            resp = requests.post(url, json=payload, headers=hdrs, timeout=120)
            if resp.ok:
                return True, resp.status_code, ""
            last_status = resp.status_code
            last_text = resp.text or ""
        except requests.RequestException as e:
            last_status = -1
            last_text = str(e)
        if attempt < retries:
            _sleep(2 ** attempt)
    return False, last_status, last_text


def _delete_existing_lefties(retries=2):
    url = f"{SUPABASE_URL}/rest/v1/player_hand_reference"
    hdrs = _headers()
    hdrs["Prefer"] = "return=minimal"
    last_status = 0
    last_text = ""
    for attempt in range(1, retries + 1):
        try:
            resp = requests.delete(url, headers=hdrs, params={"hand": "eq.L"}, timeout=60)
            if resp.ok:
                return True, resp.status_code, ""
            last_status = resp.status_code
            last_text = resp.text or ""
        except requests.RequestException as e:
            last_status = -1
            last_text = str(e)
        if attempt < retries:
            _sleep(2 ** attempt)
    return False, last_status, last_text


def _detect_player_hand_has_source_column():
    url = f"{SUPABASE_URL}/rest/v1/player_hand_reference"
    try:
        resp = requests.get(url, headers=_headers(), params={"select": "source", "limit": 1}, timeout=30)
    except requests.RequestException:
        return None
    if resp.ok:
        return True
    if _is_source_column_missing_error(resp.text):
        return False
    return None


def _fetch_existing_player_hand_sources():
    url = f"{SUPABASE_URL}/rest/v1/player_hand_reference"
    try:
        resp = requests.get(
            url,
            headers=_headers(),
            params={"select": "source", "source": "not.is.null", "limit": 2000},
            timeout=30,
        )
    except requests.RequestException:
        return []
    if not resp.ok:
        return []
    out = []
    seen = set()
    try:
        data = resp.json()
    except ValueError:
        return []
    if not isinstance(data, list):
        return []
    for row in data:
        source = row.get("source")
        if not isinstance(source, str):
            continue
        source = source.strip()
        if not source or source in seen:
            continue
        seen.add(source)
        out.append(source)
    return out


def _resolve_player_hand_source_mode(rows):
    sample = rows[: min(25, len(rows))]
    has_source_column = _detect_player_hand_has_source_column()
    candidates = []
    if has_source_column is False:
        candidates = [None]
    else:
        for value in _fetch_existing_player_hand_sources():
            if value not in candidates:
                candidates.append(value)
        for value in HAND_SOURCE_CANDIDATES:
            if value not in candidates:
                candidates.append(value)
        candidates.append(None)

    tried = []
    for source_value in candidates:
        ok, status, err_text = _post_player_hand_rows(sample, source_value, retries=1)
        label = source_value if source_value is not None else "<omit>"
        if ok:
            if tried:
                print(f"  player_hand_reference: source negotiation -> {label}")
            return source_value
        tried.append((label, status))

    if _run_hand_reference_migration():
        for source_value in ("oncourt", None):
            ok, status, err_text = _post_player_hand_rows(sample, source_value, retries=1)
            label = source_value if source_value is not None else "<omit>"
            if ok:
                print(f"  player_hand_reference: source negotiation after migration -> {label}")
                return source_value
            tried.append((f"{label} (post-migration)", status))

    summary = ", ".join(f"{label}:{status}" for label, status in tried[-8:])
    raise RuntimeError(f"source negotiation failed ({summary})")


def _load_player_hand(data_dir):
    """Load player_hand_reference from categories_atp.csv (cat1=True = left-handed)."""
    path = data_dir / "categories_atp.csv"
    if not path.exists():
        print("  player_hand_reference: SKIPPED (categories_atp.csv not found)")
        return False
    rows = []
    with open(path, "r", encoding="utf-8-sig", newline="") as f:
        for r in csv.DictReader(f):
            pid = r.get("player_id")
            if not pid:
                continue
            try:
                pid = int(pid)
            except ValueError:
                continue
            if str(r.get("cat1") or "").strip().lower() == "true":
                rows.append({"player_id": pid, "hand": "L"})

    if rows:
        known_player_ids = _load_known_player_ids(data_dir)
        if known_player_ids:
            before = len(rows)
            rows = [r for r in rows if r["player_id"] in known_player_ids]
            skipped = before - len(rows)
            if skipped:
                print(f"  player_hand_reference: skipped {skipped:,} rows (player_id missing in players_atp.csv)")

    if not rows:
        print("  player_hand_reference: 0 lefties (no cat1=True in categories_atp.csv)")
        return True
    try:
        source_mode = _resolve_player_hand_source_mode(rows)
    except RuntimeError as e:
        print(f"  ERROR: player_hand_reference: {e}")
        return False

    ok, status, err_text = _delete_existing_lefties(retries=3)
    if not ok:
        print(f"  ERROR: player_hand_reference delete existing lefties failed status={status}: {err_text[:220]}")
        return False

    for i in range(0, len(rows), BATCH):
        batch = rows[i : i + BATCH]
        ok, status, err_text = _post_player_hand_rows(batch, source_mode, retries=3)
        if not ok:
            mode = source_mode if source_mode is not None else "<omit>"
            print(f"  ERROR: player_hand_reference batch failed ({mode}) status={status}: {err_text[:220]}")
            if _is_source_constraint_error(err_text):
                print("  Hint: source constraint rejected all negotiated payloads.")
            return False
    mode = source_mode if source_mode is not None else "<omit>"
    print(f"  player_hand_reference: {len(rows):,} left-handed players (source={mode})")
    return True


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
        print("  SUPABASE_SERVICE_ROLE_KEY")
        sys.exit(1)
    if not SUPABASE_SERVICE_ROLE_KEY:
        print("ERROR: SUPABASE_SERVICE_ROLE_KEY is required for OnCourt writes.")
        print("  Refusing to fall back to the anon key because RLS blocks inserts/upserts.")
        sys.exit(1)
    if SKIP_PLAYERS and CURRENT_PLAYERS_ONLY:
        print("ERROR: --skip-players and --current-players cannot be used together.")
        sys.exit(2)

    key_type = "service_role"
    mode = "QUICK (players/tours/today only)" if QUICK else "RECENT (last 365d games/stat)" if RECENT else "FULL"
    if SKIP_PLAYERS:
        mode += " + SKIP_PLAYERS"
    elif CURRENT_PLAYERS_ONLY:
        mode += " + CURRENT_PLAYERS_ONLY"
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
    if SKIP_PLAYERS:
        print("  oncourt_players: SKIPPED (--skip-players)")
    else:
        players_rows = load_csv(DATA_DIR / "players_atp.csv")
        if CURRENT_PLAYERS_ONLY:
            today_rows = load_csv(DATA_DIR / "today_atp.csv")
            players_rows = current_fixture_player_rows(players_rows, today_rows)
            print(f"  oncourt_players: selected {len(players_rows):,} current fixture players")
        _upload_batched(
            "oncourt_players",
            players_rows,
            "id",
            lambda r: {
                "id": _safe_int(r["id"]),
                "name": r.get("name", ""),
                "birthdate": r.get("birthdate") or None,
                "country": r.get("country", ""),
                "atp_rank": _safe_int(r.get("atp_rank"), None),
                "hard_points": _safe_float(r.get("hard_points"), None),
                "clay_points": _safe_float(r.get("clay_points"), None),
                "grass_points": _safe_float(r.get("grass_points"), None),
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
            print(f"  oncourt_games: filtered {before:,} -> {len(rows):,} (since {cutoff})")
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
            print(f"  oncourt_stat: filtered {before:,} -> {len(rows):,} (since {cutoff})")
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

    # 6. player_hand_reference (lefties from categories_atp.csv, cat1=True)
    if not _load_player_hand(DATA_DIR):
        print("ERROR: player_hand_reference load failed; stopping sync to avoid stale leftie data.")
        sys.exit(1)

    # 7. Today (delete + insert fresh)
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
